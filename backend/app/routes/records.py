from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from ..extensions import db
from ..models import Ingredient, StockRecord

records_bp = Blueprint("records", __name__)


def _parse_end_of_day(value):
    if not value:
        return None
    try:
        ed = datetime.fromisoformat(value)
        if ed.hour == 0 and ed.minute == 0 and ed.second == 0 and ed.microsecond == 0:
            return ed + timedelta(days=1)
        return ed + timedelta(microseconds=1)
    except ValueError:
        return None


@records_bp.get("")
def list_records():
    record_type = request.args.get("type", "").strip()
    start_date = request.args.get("startDate", "").strip()
    end_date = request.args.get("endDate", "").strip()

    sd = None
    ed_exclusive = None
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    ed_exclusive = _parse_end_of_day(end_date)

    all_q = StockRecord.query
    if sd:
        all_q = all_q.filter(StockRecord.created_at >= sd)
    if ed_exclusive:
        all_q = all_q.filter(StockRecord.created_at < ed_exclusive)

    all_records = all_q.order_by(
        StockRecord.created_at.asc(), StockRecord.id.asc()
    ).all()

    ingredients = Ingredient.query.all()

    opening = {}
    for ing in ingredients:
        net_from_start_q = StockRecord.query.filter_by(ingredient_id=ing.id)
        if sd:
            net_from_start_q = net_from_start_q.filter(
                StockRecord.created_at >= sd
            )
        in_from_start = (
            net_from_start_q.filter_by(record_type="in")
            .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
            .scalar()
        )
        out_from_start = (
            net_from_start_q.filter_by(record_type="out")
            .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
            .scalar()
        )
        opening[ing.id] = round(
            float(ing.stock) - float(in_from_start) + float(out_from_start), 2
        )

    running = {k: float(v) for k, v in opening.items()}
    enriched_all = []
    for r in all_records:
        before = running.get(r.ingredient_id, 0.0)
        if r.record_type == "in":
            after = before + float(r.quantity)
        else:
            after = before - float(r.quantity)
        running[r.ingredient_id] = after
        d = r.to_dict()
        d["balanceBefore"] = round(before, 2)
        d["balanceAfter"] = round(after, 2)
        enriched_all.append(d)

    closing = {
        ing_id: round(val, 2) for ing_id, val in running.items()
    }

    if record_type:
        filtered = [r for r in enriched_all if r["recordType"] == record_type]
    else:
        filtered = enriched_all

    filtered.reverse()

    opening_grand = round(sum(opening.values()), 2)
    closing_grand = round(sum(closing.values()), 2)

    opening_by_ingredient = [
        {
            "ingredientId": i.id,
            "ingredientName": i.name,
            "unit": i.unit,
            "opening": opening.get(i.id, 0),
        }
        for i in ingredients
    ]

    return jsonify(
        {
            "records": filtered,
            "openingGrand": opening_grand,
            "closingGrand": closing_grand,
            "openingByIngredient": opening_by_ingredient,
        }
    )


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
    record_type = request.args.get("type", "").strip()
    start_date = request.args.get("startDate", "").strip()
    end_date = request.args.get("endDate", "").strip()

    sd = None
    ed_exclusive = None
    if start_date:
        try:
            sd = datetime.fromisoformat(start_date)
        except ValueError:
            pass
    ed_exclusive = _parse_end_of_day(end_date)

    ingredients = Ingredient.query.order_by(Ingredient.name).all()
    result = []

    for ing in ingredients:
        range_q = StockRecord.query.filter_by(ingredient_id=ing.id)
        range_q_all = StockRecord.query.filter_by(ingredient_id=ing.id)

        if sd:
            range_q = range_q.filter(StockRecord.created_at >= sd)
            range_q_all = range_q_all.filter(StockRecord.created_at >= sd)
        if ed_exclusive:
            range_q = range_q.filter(StockRecord.created_at < ed_exclusive)
            range_q_all = range_q_all.filter(StockRecord.created_at < ed_exclusive)

        if record_type:
            range_q = range_q.filter_by(record_type=record_type)

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

        total_in_all = (
            range_q_all.filter_by(record_type="in")
            .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
            .scalar()
        )
        total_out_all = (
            range_q_all.filter_by(record_type="out")
            .with_entities(func.coalesce(func.sum(StockRecord.quantity), 0))
            .scalar()
        )

        after_in = 0
        after_out = 0
        if ed_exclusive:
            after_in = (
                StockRecord.query.filter_by(
                    ingredient_id=ing.id, record_type="in"
                )
                .filter(StockRecord.created_at >= ed_exclusive)
                .with_entities(
                    func.coalesce(func.sum(StockRecord.quantity), 0)
                )
                .scalar()
            )
            after_out = (
                StockRecord.query.filter_by(
                    ingredient_id=ing.id, record_type="out"
                )
                .filter(StockRecord.created_at >= ed_exclusive)
                .with_entities(
                    func.coalesce(func.sum(StockRecord.quantity), 0)
                )
                .scalar()
            )

        opening = (
            float(ing.stock)
            - float(total_in_all)
            + float(total_out_all)
            - float(after_in)
            + float(after_out)
        )
        closing = opening + float(total_in_all) - float(total_out_all)

        result.append(
            {
                "ingredientId": ing.id,
                "ingredientName": ing.name,
                "unit": ing.unit,
                "opening": round(opening, 2),
                "totalIn": round(float(total_in), 2),
                "totalOut": round(float(total_out), 2),
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
