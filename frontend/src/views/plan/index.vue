<template>
  <section class="page" data-module="plan">
    <header class="page-head">
      <div>
        <h2>养护计划管理</h2>
        <p class="page-desc">维护养护计划，提交审批前按养护类型校验预算金额与计划工期口径，越界或撞期的先拦下再改。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记养护计划</button>
        <button class="btn" type="button" @click="exportRows">导出养护计划清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>计划编号</span>
        <input v-model="keyword" placeholder="按计划编号检索" />
      </label>
      <label class="filter-item">
        <span>计划状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ headerLabel(column) }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column" :class="{ 'reason-cell': column === '驳回理由' }">
            {{ cellText(column, row) }}
          </td>
          <td class="row-actions">
            <button
              v-for="action in rowActions(row)"
              :key="action"
              class="link"
              type="button"
              @click="handleAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无养护计划数据，可先登记养护计划</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条养护计划记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="formVisible" class="modal-mask" @click.self="closeForm">
      <div class="modal">
        <h3>{{ editingId === null ? '登记养护计划' : `修改养护计划 ${form.计划编号}` }}</h3>
        <form class="form-grid" @submit.prevent="submitForm">
          <label class="form-item">
            <span>计划编号 *</span>
            <input v-model="form.计划编号" placeholder="如 PLAN-0005" />
          </label>
          <label class="form-item">
            <span>养护类型 *</span>
            <select v-model="form.养护类型">
              <option value="">请选择养护类型</option>
              <option v-for="rule in rules" :key="rule.养护类型" :value="rule.养护类型">{{ rule.养护类型 }}</option>
            </select>
          </label>
          <label class="form-item">
            <span>养护对象 *</span>
            <input v-model="form.养护对象" placeholder="如 人民路 K2+300 段" />
          </label>
          <label class="form-item">
            <span>计划开始日期</span>
            <input v-model="form.计划开始日期" type="date" />
          </label>
          <label class="form-item">
            <span>计划工期（天）</span>
            <input v-model="form.计划工期" type="number" min="1" placeholder="如 20" />
          </label>
          <label class="form-item">
            <span>预算金额（万元）</span>
            <input v-model="form.预算金额" type="number" min="0" step="0.01" placeholder="如 12.5" />
          </label>
          <label class="form-item">
            <span>编制人员</span>
            <input v-model="form.编制人员" />
          </label>
          <label class="form-item">
            <span>审批人员</span>
            <input v-model="form.审批人员" />
          </label>
          <p v-if="selectedRule" class="rule-hint">判定口径：{{ formatRule(selectedRule) }}</p>
          <p v-else class="rule-hint">金额或工期漏填的计划不许提交；提交时会按养护类型校验口径与时间段。</p>
          <div class="modal-foot">
            <button class="btn ghost" type="button" @click="closeForm">取消</button>
            <button class="btn primary" type="submit">{{ editingId === null ? '登记' : '保存修改' }}</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="detail" class="modal-mask" @click.self="closeDetail">
      <div class="modal">
        <h3>养护计划详情 {{ detail.计划编号 }}</h3>
        <dl class="detail-grid">
          <dt>计划状态</dt>
          <dd>{{ detail.status }}</dd>
          <dt>养护类型</dt>
          <dd>{{ detail.养护类型 }}</dd>
          <dt>养护对象</dt>
          <dd>{{ detail.养护对象 }}</dd>
          <dt>计划工期</dt>
          <dd>{{ detail.计划工期 }} 天（{{ detail.计划开始日期 }} ~ {{ detail.计划结束日期 || '—' }}）</dd>
          <dt>预算金额</dt>
          <dd>{{ detail.预算金额 }} 万元</dd>
          <dt>日均预算</dt>
          <dd>{{ detail.日均预算 === null || detail.日均预算 === undefined ? '—' : `${detail.日均预算} 万元/天` }}</dd>
          <dt>编制人员</dt>
          <dd>{{ detail.编制人员 || '—' }}</dd>
          <dt>审批人员</dt>
          <dd>{{ detail.审批人员 || '—' }}</dd>
          <dt>判定口径</dt>
          <dd>{{ detail.判定口径 ? formatRule(detail.判定口径) : '该养护类型未配置口径' }}</dd>
          <template v-if="detail.status === '已驳回'">
            <dt>驳回理由</dt>
            <dd class="reject-text">{{ detail.驳回理由 }}</dd>
          </template>
        </dl>
        <div class="modal-foot">
          <button class="btn" type="button" @click="closeDetail">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>
type Detail = Record<string, any>

interface PlanRule {
  养护类型: string
  预算下限: number
  预算上限: number
  工期下限: number
  工期上限: number
  日均下限: number
  日均上限: number
}

interface PlanForm {
  计划编号: string
  养护类型: string
  养护对象: string
  计划开始日期: string
  计划工期: string
  预算金额: string
  编制人员: string
  审批人员: string
}

const ENDPOINT = '/api/plan'
const columns = ["计划编号", "养护类型", "养护对象", "计划开始日期", "计划工期", "预算金额", "编制人员", "审批人员", "计划状态", "驳回理由"]
const statuses = ["待编制", "待审批", "已批复", "已驳回", "已作废"]

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const keyword = ref('')
const statusFilter = ref('')
const rules = ref<PlanRule[]>([])
const stats = ref([
  { label: '待审批计划', value: 0 },
  { label: '已批复计划', value: 0 },
  { label: '已驳回计划', value: 0 },
])

const formVisible = ref(false)
const editingId = ref<number | null>(null)
const form = ref<PlanForm>(emptyForm())
const detail = ref<Detail | null>(null)

const selectedRule = computed(() => rules.value.find((rule) => rule.养护类型 === form.value.养护类型))

function emptyForm(): PlanForm {
  return { 计划编号: '', 养护类型: '', 养护对象: '', 计划开始日期: '', 计划工期: '', 预算金额: '', 编制人员: '', 审批人员: '' }
}

function headerLabel(column: string): string {
  if (column === '计划工期') return '计划工期（天）'
  if (column === '预算金额') return '预算金额（万元）'
  return column
}

function cellText(column: string, row: Row): string {
  if (column === '计划状态') return String(row.status ?? '—')
  const value = row[column]
  if (value === null || value === undefined || value === '') return '—'
  if (column === '计划工期') return `${value} 天`
  if (column === '预算金额') return `${value} 万元`
  return String(value)
}

function formatRule(rule: PlanRule): string {
  return `预算 ${rule.预算下限}–${rule.预算上限} 万元 · 工期 ${rule.工期下限}–${rule.工期上限} 天 · 日均 ${rule.日均下限}–${rule.日均上限} 万元/天`
}

function rowActions(row: Row): string[] {
  const status = String(row.status ?? '')
  const actions: string[] = []
  if (status === '待编制' || status === '已驳回') actions.push('提交审批', '修改')
  if (status === '待审批') actions.push('确认批复')
  if (status !== '已批复' && status !== '已作废') actions.push('作废计划')
  actions.push('详情')
  return actions
}

function handleAction(action: string, row: Row) {
  if (action === '修改') {
    openEdit(row)
    return
  }
  if (action === '详情') {
    void openDetail(row)
    return
  }
  void runAction(action, row)
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  editingId.value = null
  form.value = emptyForm()
  formVisible.value = true
}

function openEdit(row: Row) {
  editingId.value = Number(row.id)
  form.value = {
    计划编号: String(row.计划编号 ?? ''),
    养护类型: String(row.养护类型 ?? ''),
    养护对象: String(row.养护对象 ?? ''),
    计划开始日期: String(row.计划开始日期 ?? ''),
    计划工期: row.计划工期 === null || row.计划工期 === undefined ? '' : String(row.计划工期),
    预算金额: row.预算金额 === null || row.预算金额 === undefined ? '' : String(row.预算金额),
    编制人员: String(row.编制人员 ?? ''),
    审批人员: String(row.审批人员 ?? ''),
  }
  formVisible.value = true
}

function closeForm() {
  formVisible.value = false
}

function closeDetail() {
  detail.value = null
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    detail.value = await fetchJson<Detail>(`${ENDPOINT}/${row.id}`)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护计划详情读取失败'
  }
}

async function submitForm() {
  errorMessage.value = ''
  noticeMessage.value = ''
  const isEdit = editingId.value !== null
  const url = isEdit ? `${ENDPOINT}/${editingId.value}` : ENDPOINT
  try {
    const response = await request(url, {
      method: isEdit ? 'PUT' : 'POST',
      body: JSON.stringify({ values: { ...form.value } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '养护计划保存失败'
      return
    }
    noticeMessage.value = payload.message ?? '养护计划已保存'
    closeForm()
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护计划保存失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json()
    if (!payload.ok) {
      errorMessage.value = payload.message ?? '养护计划动作未生效，请稍后重试'
      return
    }
    if (payload.entry?.status === '已驳回') {
      errorMessage.value = payload.message ?? '养护计划被拦下'
    } else {
      noticeMessage.value = payload.message ?? `养护计划已${action}`
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护计划操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) query.set('keyword', keyword.value)
  if (statusFilter.value) query.set('status', statusFilter.value)
  query.set('size', '200')
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('养护计划列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    stats.value = [
      { label: '待审批计划', value: rows.value.filter((row) => row.status === '待审批').length },
      { label: '已批复计划', value: rows.value.filter((row) => row.status === '已批复').length },
      { label: '已驳回计划', value: rows.value.filter((row) => row.status === '已驳回').length },
    ]
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护计划列表读取失败'
  }
}

async function loadRules() {
  try {
    const payload = await fetchJson<{ rules: PlanRule[] }>(`${ENDPOINT}/rules`)
    rules.value = payload.rules ?? []
  } catch {
    rules.value = []
  }
}

onMounted(() => {
  void reload()
  void loadRules()
})
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  width: 560px;
  max-width: 92vw;
  max-height: 84vh;
  overflow: auto;
}
.modal h3 {
  margin: 0 0 12px;
  font-size: 15px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 12px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
}
.form-item input,
.form-item select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.rule-hint {
  grid-column: 1 / -1;
  margin: 0;
  font-size: 12px;
  color: var(--brand);
}
.modal-foot {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 6px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 8px 12px;
  margin: 0;
  font-size: 13px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
.reason-cell {
  max-width: 240px;
  color: #b42318;
}
.notice-text {
  color: #067647;
}
.reject-text {
  color: #b42318;
}
</style>
