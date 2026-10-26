<!--
  【投递列表页】系统的主页面。
    顶部：按阶段 / 状态 / 岗位筛选
    表格：每条投递的候选人、岗位、当前阶段、整体状态、AI 结果
    行内操作：通过 / 淘汰（调 advance，fromStage 用这一行的当前阶段）、撤回（调 revert）、详情
    新建投递在「候选人管理」：新建候选人时选岗位同时投递，或用 AI 录入简历
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { applicationApi, positionApi, statsApi } from '../api'
import { auth } from '../stores/auth'
import { RESULT_LABEL, STAGES, STAGE_COLOR, STAGE_LABEL, STATUSES, STATUS_LABEL, STATUS_TYPE } from '../constants'

// 终面通关（overall_status=pass）= 已入职，是流程之外的展示态，不是第 8 关
const ONBOARD = { value: 'onboard', label: '已入职' }
import { fmtTime } from '../utils/format'
import StageTag from '../components/StageTag.vue'
import ApplicationDetailView from './ApplicationDetailView.vue'

const router = useRouter()
const route = useRoute()
const refreshStats = inject('refreshStats')

// ---- 详情抽屉：点「详情」不跳页，详情整页从右侧滑出（复用 ApplicationDetailView 的嵌入模式）----
const detailVisible = ref(false)
const detailId = ref('')
const detailTab = ref('')
function openDetail(row, tab = '') {
  detailId.value = row.id
  detailTab.value = tab
  detailVisible.value = true
}

const SOURCE_LABEL = { admin: 'HR 手动', ai_intake: 'AI 录入', portal: '候选人投递' }
const SOURCE_OPTIONS = [
  { value: 'admin', label: 'HR 手动' },
  { value: 'ai_intake', label: 'AI 录入' },
  { value: 'portal', label: '候选人投递' },
]

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
  source: route.query.source || saved.source || '',
})
const list = ref([])
const loading = ref(false)
const positions = ref([])

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.stage === 'onboard') {
      params.status = 'pass' // 已入职 = 终面通关，按整体状态查
    } else {
      if (filters.stage) params.stage = filters.stage
      if (filters.status) params.status = filters.status
    }
    if (filters.pos_id) params.pos_id = filters.pos_id
    if (filters.source) params.source = filters.source
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
    if (filters.source) query.source = filters.source
    router.replace({ query })
    sessionStorage.setItem(FILTER_KEY, JSON.stringify({
      stage: filters.stage,
      status: filters.status,
      pos_id: filters.pos_id,
      source: filters.source,
    }))
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
      source: route.query.source || s.source || '',
    }
    // 只有跟当前不同才赋值，避免和上面那个 watch 打架、死循环
    if (
      next.stage !== filters.stage ||
      next.status !== filters.status ||
      next.pos_id !== filters.pos_id ||
      next.source !== filters.source
    ) {
      Object.assign(filters, next)
    }
  },
)

function resetFilters() {
  // 清空筛选：网址参数和浏览器里存的记录一起清掉，免得点回来又恢复
  sessionStorage.removeItem(FILTER_KEY)
  Object.assign(filters, { stage: '', status: '', pos_id: '', source: '' })
  // watch 会自动清空网址参数并重新查询，这里不用再手动 load
}

// ---- 行内操作：通过 / 淘汰 / 撤回 ----
// 编辑权限：候选人负责人=全部关卡；阶段负责人=本关；关卡还没负责人=可编辑（编辑即认领）
function canEditRow(row) {
  const meId = auth.user.value?.id
  if (meId == null) return true
  if (row.candidate_owner_id === meId) return true
  const sid = row.stage_owner_ids?.[row.current_stage]
  return sid == null || sid === meId
}

async function advance(row, result) {
  if (result === 'fail') {
    try {
      await ElMessageBox.confirm(
      `确定淘汰「${row.candidate_name}」？淘汰后将立即发送淘汰通知，候选人的账号会在 2 天后注销（期间登录可见通知，之后无法登录）。`,
      '淘汰确认',
      { type: 'warning', confirmButtonText: '确认淘汰', cancelButtonText: '再想想' },
    )
    } catch {
      return
    }
  }
  await applicationApi.advance(row.id, row.current_stage, result, result === 'fail')
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

const hasFilter = computed(() => filters.stage || filters.status || filters.pos_id || filters.source)

// ---- 阶段轨：7 关横排，各显示"当前卡在这一关的人数"，点一下即筛选 ----
// 数据来自 /stats/overview 的 stage_counts（只统计进行中的），与顶部指标同源
const stageCounts = ref({})
const onboardCount = ref(0)
async function loadStageCounts() {
  try {
    const d = await statsApi.overview()
    stageCounts.value = Object.fromEntries((d.stage_counts || []).map((x) => [x.stage, x.count]))
    onboardCount.value = d.pass_count || 0
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
</script>

<template>
  <div>
    <div class="page-header">
      <h2>投递列表</h2>
      <div class="muted page-tip">新建投递请到「候选人管理」：新建候选人时选岗位同时投递，或用 AI 录入简历</div>
    </div>

    <!-- 阶段轨：7 关横排，色条按关卡加深；点一下筛选该关，再点取消 -->
    <!-- tabindex：窄屏时这条横向可滚，让它能被键盘聚焦后用方向键滚动 -->
    <div class="pipeline" tabindex="0" role="group" aria-label="招聘阶段筛选">
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
      <!-- 已入职：终面通关的人，流程之外的第 8 格 -->
      <button
        type="button"
        class="pipe-stop"
        :class="{ 'is-active': filters.stage === 'onboard', 'is-empty': !onboardCount }"
        @click="toggleStage('onboard')"
      >
        <i class="pipe-bar" style="background: var(--el-color-success)" />
        <span class="pipe-name">{{ ONBOARD.label }}</span>
        <span class="pipe-count">{{ onboardCount }}</span>
      </button>
    </div>

    <!-- 工具条：状态 / 岗位 / 清空（不再是卡片，减少层级） -->
    <div class="toolbar">
      <el-select
        v-model="filters.status"
        aria-label="按状态筛选"
        placeholder="全部状态"
        clearable
        size="small"
        style="width: 132px"
      >
        <el-option v-for="s in STATUSES" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-select
        v-model="filters.pos_id"
        aria-label="按岗位筛选"
        placeholder="全部岗位"
        clearable
        filterable
        size="small"
        style="width: 200px"
      >
        <el-option v-for="p in positions" :key="p.id" :label="p.position_name" :value="p.id" />
      </el-select>
      <el-select
        v-model="filters.source"
        aria-label="按来源筛选"
        placeholder="全部来源"
        clearable
        size="small"
        style="width: 130px"
      >
        <el-option v-for="s in SOURCE_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
      </el-select>
      <el-button v-if="hasFilter" link size="small" @click="resetFilters">清空筛选</el-button>
      <span class="toolbar-count muted">共 {{ list.length }} 条</span>
    </div>

    <el-table :data="list" v-loading="loading" border :row-style="{ height: '50px' }" class="ats-vlist" empty-text="这条筛选下还没有投递记录">
      <el-table-column label="候选人" min-width="120">
        <template #default="{ row }">
          <a class="cell-link" href="javascript:;" @click="openDetail(row)">
            {{ row.candidate_name }}
          </a>
        </template>
      </el-table-column>
      <el-table-column prop="position_name" label="岗位" min-width="160" show-overflow-tooltip />
      <el-table-column label="来源" width="110">
        <template #default="{ row }">
          <el-tag
            size="small"
            effect="plain"
            :type="row.source === 'portal' ? 'success' : row.source === 'ai_intake' ? 'warning' : 'info'"
          >
            {{ SOURCE_LABEL[row.source] || row.source || 'HR 手动' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="当前阶段" width="132">
        <template #default="{ row }">
          <span v-if="row.overall_status === 'pass'" class="stage-plain onboard">
            <i class="pipe-bar" style="background: var(--el-color-success)" />
            {{ ONBOARD.label }}
          </span>
          <StageTag v-else :stage="row.current_stage" />
          <el-tooltip v-if="row.pending_notices" :content="`有 ${row.pending_notices} 条通知待发送，点击进入预览发送`" placement="top">
            <el-tag
              size="small"
              type="warning"
              effect="light"
              class="notice-badge"
              @click.stop="openDetail(row, 'notices')"
            >
              通知×{{ row.pending_notices }}
            </el-tag>
          </el-tooltip>
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
          <el-button
            link
            type="primary"
            :disabled="row.overall_status !== 'pending' || !canEditRow(row)"
            :title="canEditRow(row) ? '' : '本阶段由其他 HR 负责，你只能查看'"
            @click="advance(row, 'pass')"
          >通过</el-button>
          <el-button
            link
            type="danger"
            :disabled="row.overall_status !== 'pending' || !canEditRow(row)"
            :title="canEditRow(row) ? '' : '本阶段由其他 HR 负责，你只能查看'"
            @click="advance(row, 'fail')"
          >淘汰</el-button>
          <el-button link :disabled="!canRevert(row)" @click="revert(row)">撤回</el-button>
          <el-button link @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>



    <!-- 详情抽屉：从右侧滑出，复用投递详情整页（嵌入模式，隐藏「返回列表」） -->
    <el-drawer
      v-model="detailVisible"
      direction="rtl"
      size="60%"
      :with-header="false"
      destroy-on-close
      class="detail-drawer"
      @closed="load"
    >
      <ApplicationDetailView
        v-if="detailId"
        :key="detailId"
        :application-id="detailId"
        :initial-tab="detailTab"
        embedded
      />
    </el-drawer>
  </div>
</template>

<style scoped>
/* 已入职：与阶段色标同构的展示（绿色条 = 流程走完） */
.stage-plain.onboard {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-regular);
}
/* ---- 阶段轨：本页的主视觉，把"7 关管线"直接做成筛选器 ---- */
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
.page-tip {
  font-size: var(--ats-fs-note);
}

/* 表格里的姓名链接：用真正的 <a>（router-link），可聚焦、支持 Ctrl/中键新开 */
.cell-link {
  color: var(--el-color-primary);
  text-decoration: none;
}
.cell-link:hover {
  text-decoration: underline;
}
.cell-link:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
  border-radius: 2px;
}

.notice-badge {
  margin-left: 6px;
  cursor: pointer;
}

/* 详情抽屉：teleport 到 body，scoped 管不到，用 :global 定制外观。
   毛玻璃底用主题变量调透明度，三档主题（白天/黑夜/护眼）都成立 */
:global(.el-drawer.detail-drawer) {
  border-radius: 24px 0 0 24px;
  /* 底色染得薄（35%），轻模糊（10px）：后面的列表轮廓清楚 */
  background: color-mix(in srgb, var(--el-bg-color) 35%, transparent);
  backdrop-filter: blur(10px) saturate(1.4);
  -webkit-backdrop-filter: blur(10px) saturate(1.4);
}
</style>
