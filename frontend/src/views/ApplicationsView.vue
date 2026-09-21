<!--
  【投递列表页】系统的主页面。
    顶部：按阶段 / 状态 / 岗位筛选
    表格：每条投递的候选人、岗位、当前阶段、整体状态、AI 结果
    行内操作：通过 / 淘汰（调 advance，fromStage 用这一行的当前阶段）、撤回（调 revert）、详情
    右上角：手动新建投递（选候选人 + 选岗位；候选人可以现场新建）

  「AI 录入简历」按钮属于 M4，这里先留位置。
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { applicationApi, candidateApi, positionApi, statsApi } from '../api'
import { RESULT_LABEL, STAGES, STAGE_COLOR, STAGE_LABEL, STATUSES, STATUS_LABEL, STATUS_TYPE } from '../constants'
import { fmtTime } from '../utils/format'
import AIIntakeDialog from './AIIntakeDialog.vue'
import StageTag from '../components/StageTag.vue'

const router = useRouter()
const route = useRoute()
const refreshStats = inject('refreshStats')

// 上次用的筛选条件存这里（浏览器会话级）：从别的页面点回「投递列表」时自动恢复
const FILTER_KEY = 'ats_app_filters'
function savedFilters() {
  try {
    return JSON.parse(sessionStorage.getItem(FILTER_KEY) || '{}')
  } catch {
    return {}
  }
}

// ---- 筛选 + 列表 ----
// 初始值优先取网址参数（?stage=ai&status=pending&pos_id=1，支持刷新/收藏/分享）；
// 网址里没有就恢复上次用的筛选（从别的菜单页点回来时也能接上）
const saved = savedFilters()
const filters = reactive({
  stage: route.query.stage || saved.stage || '',
  status: route.query.status || saved.status || '',
  pos_id: route.query.pos_id ? Number(route.query.pos_id) : saved.pos_id || '',
})
const list = ref([])
const loading = ref(false)
const positions = ref([])

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.stage) params.stage = filters.stage
    if (filters.status) params.status = filters.status
    if (filters.pos_id) params.pos_id = filters.pos_id
    list.value = await applicationApi.list(params)
  } finally {
    loading.value = false
  }
}
async function loadPositions() {
  positions.value = await positionApi.list()
}

// 筛选条件一变：① 存起来（下次点回来能恢复）② 更新网址参数 ③ 重新查列表
// replace 而不是 push，避免每选一次就多一条浏览器历史
watch(
  filters,
  () => {
    const query = {}
    if (filters.stage) query.stage = filters.stage
    if (filters.status) query.status = filters.status
    if (filters.pos_id) query.pos_id = String(filters.pos_id)
    router.replace({ query })
    sessionStorage.setItem(FILTER_KEY, JSON.stringify({ stage: filters.stage, status: filters.status, pos_id: filters.pos_id }))
    load()
  },
  // immediate: 进入页面时也执行一次，保证「网址带参数进来」的筛选也会被记下来
  { deep: true, immediate: true },
)

onMounted(() => {
  loadPositions()
  loadStageCounts() // 阶段轨的每关人数
})

// 组件被复用（比如从别的菜单页点回投递列表）时，上面那段初始化不会再跑一次，
// 所以单独监听路由：每次进入这个页面，按「网址参数 → 上次存的」顺序把筛选补上。
watch(
  () => route.path,
  (path) => {
    if (path !== '/applications') return
    const s = savedFilters()
    const next = {
      stage: route.query.stage || s.stage || '',
      status: route.query.status || s.status || '',
      pos_id: route.query.pos_id ? Number(route.query.pos_id) : s.pos_id || '',
    }
    // 只有跟当前不同才赋值，避免和上面那个 watch 打架、死循环
    if (next.stage !== filters.stage || next.status !== filters.status || next.pos_id !== filters.pos_id) {
      Object.assign(filters, next)
    }
  },
)

function resetFilters() {
  // 清空筛选：网址参数和浏览器里存的记录一起清掉，免得点回来又恢复
  sessionStorage.removeItem(FILTER_KEY)
  Object.assign(filters, { stage: '', status: '', pos_id: '' })
  // watch 会自动清空网址参数并重新查询，这里不用再手动 load
}

// ---- 行内操作：通过 / 淘汰 / 撤回 ----
async function advance(row, result) {
  if (result === 'fail') {
    try {
      await ElMessageBox.confirm(`确定淘汰「${row.candidate_name}」？`, '淘汰确认', { type: 'warning' })
    } catch {
      return
    }
  }
  await applicationApi.advance(row.id, row.current_stage, result)
  ElMessage.success(result === 'pass' ? `已通过「${STAGE_LABEL[row.current_stage]}」` : '已标记淘汰')
  await load()
  loadStageCounts()
  refreshStats?.()
}

async function revert(row) {
  try {
    await ElMessageBox.confirm('撤回上一步操作？', '撤回确认', { type: 'warning' })
  } catch {
    return
  }
  await applicationApi.revert(row.id)
  ElMessage.success('已撤回')
  await load()
  loadStageCounts()
  refreshStats?.()
}

// 第一关还没打分时没有可撤的
function canRevert(row) {
  return !(row.current_stage === 'ai' && row.overall_status === 'pending')
}

// ---- 手动新建投递 ----
const createVisible = ref(false)
const createForm = reactive({ can_id: null, pos_id: null })
const createRules = {
  can_id: [{ required: true, message: '请选择候选人', trigger: 'change' }],
  pos_id: [{ required: true, message: '请选择岗位', trigger: 'change' }],
}
const createRef = ref()
const creating = ref(false)

// 候选人下拉：输入姓名时去后端模糊搜
const candidateOptions = ref([])
const searching = ref(false)
async function searchCandidates(keyword) {
  searching.value = true
  try {
    candidateOptions.value = await candidateApi.list(keyword)
  } finally {
    searching.value = false
  }
}

// 现场新建候选人（小表单，建好后自动选中）
const newCandidate = reactive({ show: false, name: '', remark: '' })
async function addCandidate() {
  if (!newCandidate.name.trim()) {
    ElMessage.warning('请输入候选人姓名')
    return
  }
  const c = await candidateApi.create({ name: newCandidate.name.trim(), remark: newCandidate.remark || null })
  candidateOptions.value = [c, ...candidateOptions.value]
  createForm.can_id = c.id
  Object.assign(newCandidate, { show: false, name: '', remark: '' })
  ElMessage.success(`候选人「${c.name}」已创建`)
}

function openCreate() {
  Object.assign(createForm, { can_id: null, pos_id: null })
  Object.assign(newCandidate, { show: false, name: '', remark: '' })
  searchCandidates('')
  createVisible.value = true
}

async function submitCreate() {
  await createRef.value.validate()
  creating.value = true
  try {
    await applicationApi.create(createForm.can_id, createForm.pos_id)
    ElMessage.success('投递已创建，当前在 AI 筛选阶段')
    createVisible.value = false
    await load()
    loadStageCounts()
    refreshStats?.()
  } finally {
    creating.value = false
  }
}

const hasFilter = computed(() => filters.stage || filters.status || filters.pos_id)

// ---- 阶段轨：8 关横排，各显示"当前卡在这一关的人数"，点一下即筛选 ----
// 数据来自 /stats/overview 的 stage_counts（只统计进行中的），与顶部指标同源
const stageCounts = ref({})
async function loadStageCounts() {
  try {
    const d = await statsApi.overview()
    stageCounts.value = Object.fromEntries((d.stage_counts || []).map((x) => [x.stage, x.count]))
  } catch {
    /* 拦截器已提示 */
  }
}
const totalInPipeline = computed(() =>
  Object.values(stageCounts.value).reduce((a, b) => a + b, 0),
)
function toggleStage(stage) {
  filters.stage = filters.stage === stage ? '' : stage
}

// ---- AI 录入弹窗 ----
const intakeVisible = ref(false)
function onIntakeClosed() {
  // AI 录完建了新投递，刷新列表、阶段轨与顶部统计
  load()
  loadPositions()
  loadStageCounts()
  refreshStats?.()
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>投递列表</h2>
      <div>
        <el-button type="success" plain @click="intakeVisible = true">
          <el-icon><MagicStick /></el-icon>&nbsp;AI 录入简历
        </el-button>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>&nbsp;手动新建投递
        </el-button>
      </div>
    </div>

    <!-- 阶段轨：8 关横排，色条按关卡加深；点一下筛选该关，再点取消 -->
    <div class="pipeline">
      <button
        type="button"
        class="pipe-all"
        :class="{ 'is-active': !filters.stage }"
        @click="filters.stage = ''"
      >
        全部
        <span class="pipe-count">{{ totalInPipeline }}</span>
      </button>
      <button
        v-for="s in STAGES"
        :key="s.value"
        type="button"
        class="pipe-stop"
        :class="{ 'is-active': filters.stage === s.value, 'is-empty': !stageCounts[s.value] }"
        @click="toggleStage(s.value)"
      >
        <i class="pipe-bar" :style="{ background: STAGE_COLOR[s.value] }" />
        <span class="pipe-name">{{ s.label }}</span>
        <span class="pipe-count">{{ stageCounts[s.value] || 0 }}</span>
      </button>
    </div>

    <!-- 工具条：状态 / 岗位 / 清空（不再是卡片，减少层级） -->
    <div class="toolbar">
      <el-select v-model="filters.status" placeholder="全部状态" clearable size="small" style="width: 132px">
        <el-option v-for="s in STATUSES" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select v-model="filters.pos_id" placeholder="全部岗位" clearable filterable size="small" style="width: 200px">
        <el-option v-for="p in positions" :key="p.id" :label="p.position_name" :value="p.id" />
      </el-select>
      <el-button v-if="hasFilter" link size="small" @click="resetFilters">清空筛选</el-button>
      <span class="toolbar-count muted">共 {{ list.length }} 条</span>
    </div>

    <el-table :data="list" v-loading="loading" border :row-style="{ height: '50px' }" empty-text="这条筛选下还没有投递记录">
      <el-table-column label="候选人" min-width="120">
        <template #default="{ row }">
          <el-link type="primary" :underline="false" @click="router.push({ name: 'application-detail', params: { id: row.id } })">
            {{ row.candidate_name }}
          </el-link>
        </template>
      </el-table-column>
      <el-table-column prop="position_name" label="岗位" min-width="160" show-overflow-tooltip />
      <el-table-column label="当前阶段" width="132">
        <template #default="{ row }">
          <StageTag :stage="row.current_stage" />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="96">
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPE[row.overall_status]" size="small" effect="light">
            {{ STATUS_LABEL[row.overall_status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="AI 结果" width="96">
        <template #default="{ row }">
          <el-tooltip v-if="row.ai_result" :content="row.ai_comment || '无理由'" placement="top" :show-after="300">
            <el-tag size="small" :type="row.ai_result === 'pass' ? 'success' : 'danger'" effect="plain">
              {{ RESULT_LABEL[row.ai_result] }}
            </el-tag>
          </el-tooltip>
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="150">
        <template #default="{ row }">
          <span class="ats-nums">{{ fmtTime(row.update_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="row.overall_status !== 'pending'" @click="advance(row, 'pass')">通过</el-button>
          <el-button link type="danger" :disabled="row.overall_status !== 'pending'" @click="advance(row, 'fail')">淘汰</el-button>
          <el-button link :disabled="!canRevert(row)" @click="revert(row)">撤回</el-button>
          <el-button link @click="router.push({ name: 'application-detail', params: { id: row.id } })">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createVisible" class="ats-dialog-narrow" title="手动新建投递" destroy-on-close>
      <el-form ref="createRef" :model="createForm" :rules="createRules" label-width="80px">
        <el-form-item label="候选人" prop="can_id">
          <div class="candidate-row">
            <el-select
              v-model="createForm.can_id"
              filterable
              remote
              :remote-method="searchCandidates"
              :loading="searching"
              placeholder="输入姓名搜索"
              style="flex: 1"
            >
              <el-option v-for="c in candidateOptions" :key="c.id" :label="c.remark ? `${c.name}（${c.remark}）` : c.name" :value="c.id" />
            </el-select>
            <el-button @click="newCandidate.show = !newCandidate.show">{{ newCandidate.show ? '收起' : '＋新建' }}</el-button>
          </div>
        </el-form-item>
        <el-form-item v-if="newCandidate.show" label="">
          <div class="new-candidate">
            <el-input v-model="newCandidate.name" placeholder="姓名" style="width: 150px" />
            <el-input v-model="newCandidate.remark" placeholder="备注（可不填）" style="flex: 1" />
            <el-button type="primary" plain @click="addCandidate">创建</el-button>
          </div>
        </el-form-item>
        <el-form-item label="岗位" prop="pos_id">
          <el-select v-model="createForm.pos_id" filterable placeholder="选择岗位" style="width: 100%">
            <el-option v-for="p in positions" :key="p.id" :label="p.position_name" :value="p.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- AI 录入简历弹窗 -->
    <AIIntakeDialog :visible="intakeVisible" @close="onIntakeClosed" />
  </div>
</template>

<style scoped>
/* ---- 阶段轨：本页的主视觉，把"8 关管线"直接做成筛选器 ---- */
.pipeline {
  display: flex;
  align-items: stretch;
  gap: 2px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: 4px;
  margin-bottom: var(--ats-sp-3);
  overflow-x: auto;
}
.pipe-stop,
.pipe-all {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border: none;
  border-radius: var(--ats-radius-sm);
  background: none;
  cursor: pointer;
  font-family: inherit;
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-regular);
  white-space: nowrap;
  transition: background-color 0.15s;
}
.pipe-stop:hover,
.pipe-all:hover {
  background: var(--el-fill-color-light);
}
.pipe-stop:focus-visible,
.pipe-all:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}
.pipe-stop.is-active,
.pipe-all.is-active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: var(--ats-fw-medium);
}
.pipe-stop.is-empty {
  opacity: 0.5;
}
.pipe-bar {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  flex: none;
}
.pipe-count {
  font-variant-numeric: var(--ats-nums);
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-secondary);
  min-width: 16px;
  text-align: right;
}
.pipe-stop.is-active .pipe-count,
.pipe-all.is-active .pipe-count {
  color: var(--el-color-primary);
}

/* ---- 工具条 ---- */
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
  margin-bottom: var(--ats-sp-3);
}
.toolbar-count {
  margin-left: auto;
}

.candidate-row,
.new-candidate {
  display: flex;
  gap: 8px;
  width: 100%;
}
</style>
