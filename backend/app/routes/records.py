from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import Ingredient, StockRecord

records_bp = Blueprint("records", __name__)


@records_bp.get("")
def list_records():
    record_type = request.args.get("type", "").strip()
    start_date = request.args.get("startDate", "").strip()
    end_date = request.args.get("endDate", "").strip()
    query = StockRecord.query
    if record_type:
        query = query.filter_by(record_type=record_type)
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
            query = query.filter(StockRecord.created_at >= sd)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
            query = query.filter(StockRecord.created_at <= ed)
        except ValueError:
            pass
    records = query.order_by(StockRecord.created_at.desc()).all()
    return jsonify([record.to_dict() for record in records])


@records_bp.post("")
def create_record():
    data = request.get_json() or {}
    ingredient = Ingredient.query.get_or_404(data["ingredientId"])
    quantity = float(data["quantity"])
    record_type = data["recordType"]

    if record_type == "in":
        ingredient.stock += quantity
    elif record_type == "out":
        if ingredient.stock < quantity:
            return {"message": "库存不足，无法出库"}, 400
        ingredient.stock -= quantity
    else:
        return {"message": "recordType 必须是 in 或 out"}, 400

    record = StockRecord(
        ingredient_id=ingredient.id,
        record_type=record_type,
        quantity=quantity,
        operator=data.get("operator", "系统管理员"),
        source=data.get("source"),
        note=data.get("note"),
    )
    db.session.add(record)
    db.session.commit()
    return record.to_dict(), 201


@records_bp.get("/summary")
def records_summary():
    start_date = request.args.get("startDate", "").strip()
    end_date = request.args.get("endDate", "").strip()

    sd = None
    ed = None
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    if end_date:
        try:
            ed = datetime.fromisoformat(end_date)
        except ValueError:
            pass

    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    result = []

    for ing in ingredients:
        range_q = StockRecord.query.filter_by(ingredient_id=ing.id)

        if sd:
            range_q = range_q.filter(StockRecord.created_at >= sd)
        if ed:
            range_q = range_q.filter(StockRecord.created_at <= ed)

        total_in = (
            range_q.filter_by(record_type="in")
            .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
            .scalar()
        )
        total_out = (
            range_q.filter_by(record_type="out")
            .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
            .scalar()
        )

        after_in = 0
        after_out = 0
        if ed:
            after_in = (
                StockRecord.query.filter_by(ingredient_id=ing.id, record_type="in")
                .filter(StockRecord.created_at > ed)
                .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
                .scalar()
            )
            after_out = (
                StockRecord.query.filter_by(ingredient_id=ing.id, record_type="out")
                .filter(StockRecord.created_at > ed)
                .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
                .scalar()
            )

        opening = ing.stock - total_in + total_out - after_in + after_out
        closing = opening + total_in - total_out

        result.append(
            {
                "ingredientId": ing.id,
                "ingredientName": ing.name,
                "unit": ing.unit,
                "opening": round(opening, 2),
                "totalIn": round(total_in, 2),
                "totalOut": round(total_out, 2),
                "closing": round(closing, 2),
            }
        )

    grand_opening = round(sum(r["opening"] for r in result), 2)
    grand_in = round(sum(r["totalIn"] for r in result), 2)
    grand_out = round(sum(r["totalOut"] for r in result), 2)
    grand_closing = round(sum(r["closing"] for r in result), 2)

    return {
        "items": result,
        "grand": {
            "opening": grand_opening,
            "totalIn": grand_in,
            "totalOut": grand_out,
            "closing": grand_closing,
        },
    }
