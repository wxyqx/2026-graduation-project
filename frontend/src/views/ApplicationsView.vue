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

import { applicationApi, candidateApi, positionApi } from '../api'
import { RESULT_LABEL, STAGES, STAGE_LABEL, STATUSES, STATUS_LABEL, STATUS_TYPE } from '../constants'
import { fmtTime } from '../utils/format'
import AIIntakeDialog from './AIIntakeDialog.vue'

const router = useRouter()
const route = useRoute()
const refreshStats = inject('refreshStats')

// ---- 筛选 + 列表 ----
// 初始值从网址参数里读（?stage=ai&status=pending&pos_id=1），这样刷新/收藏后筛选条件不丢
const filters = reactive({
  stage: route.query.stage || '',
  status: route.query.status || '',
  pos_id: route.query.pos_id ? Number(route.query.pos_id) : '',
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

// 筛选条件一变：① 更新网址参数（刷新后能还原）② 重新查列表
// replace 而不是 push，避免每选一次就多一条浏览器历史
watch(
  filters,
  () => {
    const query = {}
    if (filters.stage) query.stage = filters.stage
    if (filters.status) query.status = filters.status
    if (filters.pos_id) query.pos_id = String(filters.pos_id)
    router.replace({ query })
    load()
  },
  { deep: true },
)

onMounted(() => {
  load()
  loadPositions()
})

function resetFilters() {
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
    refreshStats?.()
  } finally {
    creating.value = false
  }
}

const hasFilter = computed(() => filters.stage || filters.status || filters.pos_id)

// ---- AI 录入弹窗 ----
const intakeVisible = ref(false)
function onIntakeClosed() {
  // AI 录完建了新投递，刷新列表和顶部统计
  load()
  loadPositions()
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

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="阶段">
          <el-select v-model="filters.stage" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="s in STAGES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 130px">
            <el-option v-for="s in STATUSES" :key="s.value" :label="s.label" :value="s.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="岗位">
          <el-select v-model="filters.pos_id" placeholder="全部" clearable filterable style="width: 200px">
            <el-option v-for="p in positions" :key="p.id" :label="p.position_name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="hasFilter">
          <el-button link @click="resetFilters">清空筛选</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" border :row-style="{ height: '52px' }" empty-text="暂无投递记录">
        <el-table-column prop="candidate_name" label="候选人" min-width="120" />
        <el-table-column prop="position_name" label="岗位" min-width="160" />
        <el-table-column label="当前阶段" width="120">
          <template #default="{ row }">
            <el-tag effect="plain">{{ STAGE_LABEL[row.current_stage] || row.current_stage }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="STATUS_TYPE[row.overall_status]">{{ STATUS_LABEL[row.overall_status] }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="AI 结果" width="100">
          <template #default="{ row }">
            <el-tooltip v-if="row.ai_result" :content="row.ai_comment || '无理由'" placement="top" :show-after="300">
              <el-tag size="small" :type="row.ai_result === 'pass' ? 'success' : 'danger'" effect="light">
                {{ RESULT_LABEL[row.ai_result] }}
              </el-tag>
            </el-tooltip>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.update_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button link type="success" :disabled="row.overall_status !== 'pending'" @click="advance(row, 'pass')">通过</el-button>
            <el-button link type="danger" :disabled="row.overall_status !== 'pending'" @click="advance(row, 'fail')">淘汰</el-button>
            <el-button link type="warning" :disabled="!canRevert(row)" @click="revert(row)">撤回</el-button>
            <el-button link @click="router.push({ name: 'application-detail', params: { id: row.id } })">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createVisible" title="手动新建投递" width="520px" destroy-on-close>
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
.filter-card {
  margin-bottom: 14px;
}
.filter-card :deep(.el-form-item) {
  margin-bottom: 0;
}
.muted {
  color: var(--el-text-color-secondary);
}
.candidate-row,
.new-candidate {
  display: flex;
  gap: 8px;
  width: 100%;
}
</style>
