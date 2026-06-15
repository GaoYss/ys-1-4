<template>
  <section>
    <PageHeader eyebrow="Stock Records" title="入库出库记录">
      <button class="primary-btn" @click="submitRecord">登记</button>
    </PageHeader>

    <section class="form-panel">
      <div class="form-grid">
        <label>
          起始日期
          <input v-model="filter.startDate" type="date" @change="onFilterChange" />
        </label>
        <label>
          截止日期
          <input v-model="filter.endDate" type="date" @change="onFilterChange" />
        </label>
        <label class="checkbox-line" style="align-self:end">
          <button class="secondary-btn" @click="resetFilter">重置</button>
        </label>
      </div>
    </section>

    <div v-if="summary" class="metrics-grid">
      <div class="metric">
        <span>期初库存</span>
        <strong>{{ summary.grand.opening }}</strong>
      </div>
      <div class="metric">
        <span>入库合计</span>
        <strong>{{ summary.grand.totalIn }}</strong>
      </div>
      <div class="metric">
        <span>出库合计</span>
        <strong>{{ summary.grand.totalOut }}</strong>
      </div>
      <div class="metric">
        <span>期末库存</span>
        <strong>{{ summary.grand.closing }}</strong>
      </div>
    </div>

    <section v-if="summary && summary.items.length" class="panel" style="margin-bottom:18px">
      <h2>各原料汇总</h2>
      <DataTable :columns="summaryColumns" :rows="summary.items">
        <template #opening="{ row }">{{ row.opening }} {{ row.unit }}</template>
        <template #totalIn="{ row }">{{ row.totalIn }} {{ row.unit }}</template>
        <template #totalOut="{ row }">{{ row.totalOut }} {{ row.unit }}</template>
        <template #closing="{ row }">{{ row.closing }} {{ row.unit }}</template>
      </DataTable>
    </section>

    <section class="form-panel">
      <h2 style="margin:0 0 14px;font-size:16px">新增记录</h2>
      <div class="form-grid">
        <label>
          原料
          <select v-model.number="form.ingredientId">
            <option disabled :value="null">选择原料</option>
            <option v-for="item in ingredients" :key="item.id" :value="item.id">
              {{ item.name }} / 库存 {{ item.stock }} {{ item.unit }}
            </option>
          </select>
        </label>
        <label>
          类型
          <select v-model="form.recordType">
            <option value="in">入库</option>
            <option value="out">出库</option>
          </select>
        </label>
        <label>
          数量
          <input v-model.number="form.quantity" type="number" min="1" />
        </label>
        <label>
          经办人
          <input v-model="form.operator" />
        </label>
        <label>
          来源/用途
          <input v-model="form.source" />
        </label>
        <label>
          备注
          <input v-model="form.note" />
        </label>
      </div>
    </section>

    <p v-if="error" class="error-text">{{ error }}</p>

    <DataTable :columns="columns" :rows="records">
      <template #recordType="{ row }">
        <StatusBadge
          :label="row.recordType === 'in' ? '入库' : '出库'"
          :variant="row.recordType === 'in' ? 'success' : 'warning'"
        />
      </template>
      <template #quantity="{ row }">{{ row.quantity }} {{ row.unit }}</template>
      <template #createdAt="{ row }">{{ formatDateTime(row.createdAt) }}</template>
    </DataTable>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'

import { inventoryApi } from '../api/inventory'
import { recordsApi } from '../api/records'
import DataTable from '../components/DataTable.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { formatDateTime } from '../utils/format'

const records = ref([])
const ingredients = ref([])
const summary = ref(null)
const error = ref('')

const filter = reactive({
  startDate: '',
  endDate: ''
})

const form = reactive({
  ingredientId: null,
  recordType: 'in',
  quantity: 1,
  operator: '系统管理员',
  source: '',
  note: ''
})

const columns = [
  { key: 'ingredientName', label: '原料' },
  { key: 'recordType', label: '类型' },
  { key: 'quantity', label: '数量' },
  { key: 'operator', label: '经办人' },
  { key: 'source', label: '来源/用途' },
  { key: 'createdAt', label: '时间' }
]

const summaryColumns = [
  { key: 'ingredientName', label: '原料' },
  { key: 'opening', label: '期初' },
  { key: 'totalIn', label: '入库' },
  { key: 'totalOut', label: '出库' },
  { key: 'closing', label: '期末' }
]

function buildParams() {
  const params = {}
  if (filter.startDate) params.startDate = filter.startDate
  if (filter.endDate) params.endDate = filter.endDate + 'T23:59:59'
  return params
}

async function loadRecords() {
  const res = await recordsApi.list(buildParams())
  records.value = res.data
}

async function loadSummary() {
  const res = await recordsApi.summary(buildParams())
  summary.value = res.data
}

async function loadOptions() {
  const res = await inventoryApi.options()
  ingredients.value = res.data.ingredients
}

async function onFilterChange() {
  await Promise.all([loadRecords(), loadSummary()])
}

function resetFilter() {
  filter.startDate = ''
  filter.endDate = ''
  onFilterChange()
}

async function submitRecord() {
  error.value = ''
  try {
    await recordsApi.create({ ...form })
    Object.assign(form, {
      ingredientId: null,
      recordType: 'in',
      quantity: 1,
      operator: '系统管理员',
      source: '',
      note: ''
    })
    await Promise.all([loadRecords(), loadOptions(), loadSummary()])
  } catch (err) {
    error.value = err.response?.data?.message || '登记失败'
  }
}

onMounted(async () => {
  await Promise.all([loadRecords(), loadOptions(), loadSummary()])
})
</script>
