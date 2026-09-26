<template>
  <section class="page" data-module="plan">
    <header class="page-head">
      <div>
        <h2>养护计划管理</h2>
        <p class="page-desc">维护养护计划，围绕计划编号、养护类型、养护对象、计划工期做登记、筛选与状态流转；提交审批前按判定口径校验预算与工期。</p>
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

    <section class="rule-panel">
      <h3>提交判定口径（越出范围或金额与工期冲突的计划会被拦下）</h3>
      <table class="rule-table">
        <thead>
          <tr>
            <th>养护类型</th>
            <th>预算金额</th>
            <th>计划工期</th>
            <th>日均费用</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="rule in rules" :key="rule.养护类型">
            <td>{{ rule.养护类型 }}</td>
            <td>{{ rule.预算金额范围 }}</td>
            <td>{{ rule.计划工期范围 }}</td>
            <td>{{ rule.日均费用范围 }}</td>
          </tr>
        </tbody>
      </table>
    </section>

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
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column" :class="{ 'reject-text': column === '驳回理由' && row[column] }">
            {{ row[column] || '—' }}
          </td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-if="editableStatuses.includes(String(row.status))"
              class="link"
              type="button"
              @click="openEdit(row)"
            >
              修改
            </button>
            <button
              v-if="submittableStatuses.includes(String(row.status))"
              class="link"
              type="button"
              @click="runAction('提交审批', row)"
            >
              提交审批
            </button>
            <button
              v-if="row.status === '待审批'"
              class="link"
              type="button"
              @click="runAction('确认批复', row)"
            >
              确认批复
            </button>
            <button
              v-if="row.status !== '已作废'"
              class="link"
              type="button"
              @click="runAction('作废计划', row)"
            >
              作废计划
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

    <div v-if="dialogMode" class="modal-mask" @click.self="closeDialog">
      <form class="modal-card" @submit.prevent="submitDialog">
        <h3>{{ dialogMode === 'create' ? '登记养护计划' : `修改养护计划 ${form.计划编号}` }}</h3>
        <label v-if="dialogMode === 'create'" class="form-item">
          <span>计划编号 *</span>
          <input v-model.trim="form.计划编号" placeholder="如 PLAN-0005" />
        </label>
        <label class="form-item">
          <span>养护类型 *</span>
          <input v-model.trim="form.养护类型" list="plan-type-options" placeholder="选择或输入养护类型" />
          <datalist id="plan-type-options">
            <option v-for="item in typeOptions" :key="item" :value="item" />
          </datalist>
        </label>
        <p v-if="currentRuleHint" class="rule-hint">{{ currentRuleHint }}</p>
        <label class="form-item">
          <span>养护对象 *</span>
          <input v-model.trim="form.养护对象" placeholder="如 人民路（K0+000~K2+300）" />
        </label>
        <label class="form-item">
          <span>计划开始日期</span>
          <input v-model="form.计划开始日期" type="date" />
        </label>
        <label class="form-item">
          <span>计划工期（天）</span>
          <input v-model="form.计划工期" type="number" min="1" step="1" placeholder="如 30" />
        </label>
        <label class="form-item">
          <span>预算金额（万元）</span>
          <input v-model="form.预算金额" type="number" min="0" step="0.01" placeholder="如 12.5" />
        </label>
        <label class="form-item">
          <span>编制人员</span>
          <input v-model.trim="form.编制人员" />
        </label>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <div class="modal-actions">
          <button class="btn primary" type="submit">{{ dialogMode === 'create' ? '登记' : '保存修改' }}</button>
          <button class="btn ghost" type="button" @click="closeDialog">取消</button>
        </div>
      </form>
    </div>

    <div v-if="detailEntry" class="modal-mask" @click.self="detailEntry = null">
      <section class="modal-card">
        <h3>养护计划详情</h3>
        <dl class="detail-list">
          <template v-for="field in detailFields" :key="field">
            <dt>{{ field }}</dt>
            <dd :class="{ 'reject-text': field === '驳回理由' && detailEntry[field] }">
              {{ detailEntry[field] || '—' }}
            </dd>
          </template>
        </dl>
        <div class="modal-actions">
          <button class="btn" type="button" @click="detailEntry = null">关闭</button>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

interface RuleItem {
  养护类型: string
  预算金额范围: string
  计划工期范围: string
  日均费用范围: string
}

const ENDPOINT = '/api/plan'
const columns = ["计划编号", "养护类型", "养护对象", "计划开始日期", "计划工期", "预算金额", "编制人员", "审批人员", "计划状态", "驳回理由"]
// 详情页字段与列表保持一致，工期、状态、驳回理由看到的是同一条记录
const detailFields = columns
const statuses = ["待编制", "待审批", "已批复", "已驳回", "已作废"]
const submittableStatuses = ["待编制", "已驳回"]
const editableStatuses = ["待编制", "已驳回"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref([{ label: "待审批计划", value: 0 }, { label: "已批复计划", value: 0 }, { label: "本月计划金额", value: 0 }])
const rules = ref<RuleItem[]>([])
const keyword = ref('')
const statusFilter = ref('')
const errorMessage = ref('')
const noticeMessage = ref('')

const dialogMode = ref<'' | 'create' | 'edit'>('')
const editingId = ref<number | null>(null)
const dialogError = ref('')
const emptyForm = { 计划编号: '', 养护类型: '', 养护对象: '', 计划开始日期: '', 计划工期: '', 预算金额: '', 编制人员: '' }
const form = reactive({ ...emptyForm })

const detailEntry = ref<Row | null>(null)

const typeOptions = computed(() => rules.value.filter((rule) => !rule.养护类型.startsWith('其他')).map((rule) => rule.养护类型))
const currentRuleHint = computed(() => {
  const rule = rules.value.find((item) => item.养护类型 === form.养护类型)
    ?? rules.value.find((item) => item.养护类型.startsWith('其他'))
  return rule ? `口径参考：预算 ${rule.预算金额范围}，工期 ${rule.计划工期范围}，日均 ${rule.日均费用范围}` : ''
})

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  Object.assign(form, emptyForm)
  editingId.value = null
  dialogError.value = ''
  dialogMode.value = 'create'
}

function openEdit(row: Row) {
  Object.assign(form, {
    计划编号: String(row.计划编号 ?? ''),
    养护类型: String(row.养护类型 ?? ''),
    养护对象: String(row.养护对象 ?? ''),
    计划开始日期: String(row.计划开始日期 ?? ''),
    计划工期: String(row.计划工期 ?? '').replace('天', ''),
    预算金额: row.预算金额 === null || row.预算金额 === undefined ? '' : String(row.预算金额),
    编制人员: String(row.编制人员 ?? ''),
  })
  editingId.value = Number(row.id)
  dialogError.value = ''
  dialogMode.value = 'edit'
}

function closeDialog() {
  dialogMode.value = ''
  dialogError.value = ''
}

async function submitDialog() {
  dialogError.value = ''
  const values: Row = {
    养护类型: form.养护类型,
    养护对象: form.养护对象,
    计划开始日期: form.计划开始日期,
    计划工期: form.计划工期 === '' ? '' : `${form.计划工期}天`,
    预算金额: form.预算金额 === '' ? '' : Number(form.预算金额),
    编制人员: form.编制人员,
  }
  const isCreate = dialogMode.value === 'create'
  if (isCreate) {
    values.计划编号 = form.计划编号
  }
  const url = isCreate ? ENDPOINT : `${ENDPOINT}/${editingId.value}`
  try {
    const response = await request(url, {
      method: isCreate ? 'POST' : 'PUT',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      dialogError.value = payload.message ?? payload.detail ?? '养护计划保存失败'
      return
    }
    noticeMessage.value = payload.message ?? '养护计划已保存'
    closeDialog()
    await refreshAll()
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '养护计划保存失败'
  }
}

async function openDetail(row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('养护计划详情读取失败')
    }
    detailEntry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护计划详情读取失败'
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
    if (!response.ok) {
      throw new Error(payload.detail ?? '养护计划动作未生效，请稍后重试')
    }
    if (payload.ok) {
      noticeMessage.value = payload.message ?? `养护计划已${action}`
    } else {
      errorMessage.value = payload.message ?? '养护计划动作未生效'
    }
    await refreshAll()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护计划操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (keyword.value) {
    query.set('keyword', keyword.value)
  }
  if (statusFilter.value) {
    query.set('status', statusFilter.value)
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('养护计划列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '养护计划列表读取失败'
  }
}

async function refreshStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) {
      return
    }
    const payload = await response.json()
    const all: Row[] = payload.items ?? []
    const month = new Date().toISOString().slice(0, 7)
    const monthAmount = all
      .filter((row) => row.status !== '已作废' && String(row.计划开始日期 ?? '').startsWith(month))
      .reduce((sum, row) => sum + (Number(row.预算金额) || 0), 0)
    stats.value = [
      { label: '待审批计划', value: all.filter((row) => row.status === '待审批').length },
      { label: '已批复计划', value: all.filter((row) => row.status === '已批复').length },
      { label: '本月计划金额', value: Math.round(monthAmount * 100) / 100 },
    ]
  } catch {
    // 统计卡片刷新失败不阻断列表
  }
}

async function loadRules() {
  try {
    const response = await request(`${ENDPOINT}/rules`)
    if (!response.ok) {
      return
    }
    const payload = await response.json()
    rules.value = payload.rules ?? []
  } catch {
    // 判定口径展示失败不阻断页面
  }
}

async function refreshAll() {
  await Promise.all([reload(), refreshStats()])
}

onMounted(() => {
  void refreshAll()
  void loadRules()
})
</script>

<style scoped>
.rule-panel { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 10px 12px; margin-bottom: 12px; }
.rule-panel h3 { margin: 0 0 8px; font-size: 13px; }
.rule-table { width: 100%; border-collapse: collapse; }
.rule-table th, .rule-table td { border: 1px solid var(--border); padding: 6px 8px; font-size: 12px; text-align: left; }
.notice-text { color: #067647; }
.reject-text { color: #b42318; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 10; }
.modal-card { background: #fff; border-radius: 10px; padding: 16px 18px; width: 420px; max-width: 92vw; max-height: 88vh; overflow: auto; display: flex; flex-direction: column; gap: 10px; }
.modal-card h3 { margin: 0; font-size: 15px; }
.form-item span { display: block; font-size: 12px; color: var(--muted); margin-bottom: 2px; }
.form-item input { width: 100%; padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px; }
.rule-hint { margin: 0; font-size: 12px; color: var(--muted); }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
.detail-list { display: grid; grid-template-columns: 96px 1fr; gap: 6px 12px; margin: 0; font-size: 13px; }
.detail-list dt { color: var(--muted); }
.detail-list dd { margin: 0; word-break: break-all; }
</style>
