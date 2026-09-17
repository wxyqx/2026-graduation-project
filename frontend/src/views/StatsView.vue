<!--
  【汇总导出页】
  上半部分：统计卡 —— 数据来自 /stats/overview。
    5 张大数字卡 + 8 关人数分布条 + 按岗位分组小表
  下半部分：导出面板 —— 选范围 → 勾字段 → 选格式 → 导出 xlsx/csv 下载。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { exportFields, exportFile, positionApi, settingsApi, statsApi } from '../api'
import { STAGES, STAGE_LABEL, STATUSES } from '../constants'
import { downloadBlob } from '../utils/download'

const router = useRouter()
const refreshStats = inject('refreshStats')

// 阶段多选（用于「进行中名单」筛选）：默认全选
const STAGE_OPTIONS = STAGES.map((s) => ({ value: s.value, label: s.label }))
const pickedStages = ref(STAGES.map((s) => s.value))
// 阶段勾选一变就重新取名单（用 watch：手动选和程序改都生效）
watch(pickedStages, () => loadProgress(), { deep: true })

// 格子点开看名单
const cellVisible = ref(false)
const cellLoading = ref(false)
const cellData = ref(null)

async function openCell(rowKey, posId) {
  if (posId == null) return
  cellLoading.value = true
  cellVisible.value = true
  cellData.value = null
  try {
    const params = { row: rowKey, pos_id: posId, ...rangeParams() }
    cellData.value = await statsApi.matrixCell(params)
  } finally {
    cellLoading.value = false
  }
}
function gotoApp(appId) {
  cellVisible.value = false
  router.push({ name: 'application-detail', params: { id: appId } })
}

// ---- 统计 ----
const stats = ref(null)
const loading = ref(false)
async function loadStats() {
  loading.value = true
  try {
    stats.value = await statsApi.overview()
  } finally {
    loading.value = false
  }
}
onMounted(loadStats)

const statCards = computed(() => {
  const s = stats.value
  if (!s) return []
  return [
    { label: '在招岗位', value: s.position_count, icon: 'Briefcase', color: '#409eff' },
    { label: '进行中', value: s.pending_count, icon: 'Loading', color: '#e6a23c' },
    { label: '已录用', value: s.pass_count, icon: 'CircleCheck', color: '#67c23a' },
    { label: '已淘汰', value: s.fail_count, icon: 'CircleClose', color: '#f56c6c' },
    { label: '本月录用', value: s.month_hired, icon: 'Calendar', color: '#909399' },
  ]
})

// 8 关分布条：算好每关的百分比宽度
const maxStageCount = computed(() => Math.max(1, ...(stats.value?.stage_counts.map((x) => x.count) || [0])))
function stagePct(count) {
  return Math.round((count / maxStageCount.value) * 100)
}

// ---- 阶段 × 岗位 交叉汇总表（周报那种表）----
const RANGES = [
  { value: 'week', label: '本周' },
  { value: 'last_week', label: '上周' },
  { value: 'month', label: '本月' },
  { value: 'all', label: '全部' },
  { value: 'custom', label: '自定义' },
]
const matrixRange = reactive({ range: 'week', start_date: null, end_date: null })
const matrix = ref(null)
const matrixLoading = ref(false)
const exportingMatrix = ref(false)

// 时间范围参数（交叉表和进行中清单共用）
function rangeParams() {
  const params = { range: matrixRange.range }
  if (matrixRange.range === 'custom') {
    if (matrixRange.start_date) params.start_date = matrixRange.start_date
    if (matrixRange.end_date) params.end_date = matrixRange.end_date
  }
  return params
}

async function loadMatrix() {
  matrixLoading.value = true
  try {
    matrix.value = await statsApi.matrix(rangeParams())
  } finally {
    matrixLoading.value = false
  }
}

// 范围一变：两块表一起刷新（联动）
function reloadAll() {
  loadMatrix()
  loadProgress()
}

// ---- 进行中的候选人所处阶段（周报第二张表）----
const progress = ref(null)
const progressLoading = ref(false)
const editingAppId = ref(null) // 正在编辑阶段的那一行
// 把分组拍平成表格行（岗位每行都显示，与截图一致）
const progressRows = computed(() => {
  const out = []
  for (const g of progress.value?.groups || []) {
    for (const c of g.candidates) {
      out.push({ ...c, position_label: g.position_label })
    }
  }
  return out
})
const editingText = ref('')
const savingNote = ref(false)
const exportingReport = ref(false)

async function loadProgress() {
  progressLoading.value = true
  try {
    // 阶段多选传给后端；全选时不传（等于不筛）
    const params = rangeParams()
    if (pickedStages.value.length && pickedStages.value.length < STAGES.length) {
      params.stages = pickedStages.value
    }
    progress.value = await statsApi.inProgress(params)
  } finally {
    progressLoading.value = false
  }
}

// 点某行的「阶段」→ 进入编辑
function startEdit(row) {
  editingAppId.value = row.app_id
  editingText.value = row.stage_text
}
function cancelEdit() {
  editingAppId.value = null
  editingText.value = ''
}
// 保存手动文案（传空 = 恢复自动）
async function saveNote(appId, text) {
  savingNote.value = true
  try {
    await settingsApi.saveStageNote(appId, text)
    ElMessage.success(text ? '阶段文案已保存' : '已恢复自动生成')
    cancelEdit()
    await loadProgress()
  } finally {
    savingNote.value = false
  }
}

// 导出完整周报（两个工作表）
async function exportReport() {
  exportingReport.value = true
  try {
    const filters = {}
    if (matrixRange.range === 'custom') {
      filters.start_date = matrixRange.start_date || null
      filters.end_date = matrixRange.end_date || null
    }
    const { blob, filename, rowCount } = await exportFile(filters, [], 'xlsx', 'report', matrixRange.range)
    downloadBlob(blob, filename)
    ElMessage.success(`已导出招聘周报（${rowCount} 行）`)
  } finally {
    exportingReport.value = false
  }
}

onMounted(() => {
  loadMatrix()
  loadProgress()
})

// 导出这张交叉表
async function exportMatrix() {
  exportingMatrix.value = true
  try {
    const filters = {}
    if (matrixRange.range === 'custom') {
      filters.start_date = matrixRange.start_date || null
      filters.end_date = matrixRange.end_date || null
    }
    const { blob, filename, rowCount } = await exportFile(filters, [], 'xlsx', 'matrix', matrixRange.range)
    downloadBlob(blob, filename)
    ElMessage.success(`已导出交叉汇总表（${rowCount} 行）`)
  } finally {
    exportingMatrix.value = false
  }
}

// ---- 导出 ----
const positions = ref([])
const fieldDefs = ref([]) // 后端给的全字段 [{key,label}]
const allFields = ref([]) // 当前勾选
const exporting = ref(false)

const exportForm = reactive({
  start_date: null,
  end_date: null,
  pos_id: null,
  stage: '',
  status: '',
  format: 'xlsx',
})

// 字段分组展示用的中文分组名
const GROUP = {
  base: '基本信息',
  result: '各关结果',
  time: '时间',
}
function fieldGroup(key) {
  if (['id', 'candidate_name', 'position_name', 'current_stage', 'overall_status', 'ai_comment'].includes(key)) return 'base'
  if (key.endsWith('_time')) return 'time'
  return 'result'
}
const groupedFields = computed(() => {
  const groups = { base: [], result: [], time: [] }
  for (const f of fieldDefs.value) groups[fieldGroup(f.key)].push(f)
  return groups
})

async function initExport() {
  const [ps, fs] = await Promise.all([positionApi.list(), exportFields()])
  positions.value = ps
  fieldDefs.value = fs
  allFields.value = fs.map((f) => f.key) // 默认全选
}
onMounted(() => {
  loadStats()
  initExport()
})

function toggleAll() {
  allFields.value = allFields.value.length === fieldDefs.value.length ? [] : fieldDefs.value.map((f) => f.key)
}

async function doExport() {
  exporting.value = true
  try {
    const filters = {
      start_date: exportForm.start_date || null,
      end_date: exportForm.end_date || null,
      pos_id: exportForm.pos_id || null,
      stage: exportForm.stage || null,
      status: exportForm.status || null,
    }
    const { blob, filename, rowCount } = await exportFile(filters, allFields.value, exportForm.format)
    downloadBlob(blob, filename)
    ElMessage.success(`已导出 ${rowCount} 行（${exportForm.format.toUpperCase()}）`)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header"><h2>汇总导出</h2></div>

    <!-- 统计卡：5 张平均占满一行 -->
    <div class="stat-cards">
      <el-card v-for="c in statCards" :key="c.label" shadow="never" class="stat-card">
        <div class="stat-inner">
          <el-icon :size="30" :style="{ color: c.color }"><component :is="c.icon" /></el-icon>
          <div>
            <div class="stat-value">{{ c.value }}</div>
            <div class="stat-label">{{ c.label }}</div>
          </div>
        </div>
      </el-card>
    </div>

    <el-row :gutter="14">
      <el-col :span="10">
        <!-- 各关人数分布 -->
        <el-card shadow="never">
          <template #header>各阶段进行中人数</template>
          <div v-for="s in stats?.stage_counts || []" :key="s.stage" class="stage-bar">
            <span class="stage-name">{{ s.label }}</span>
            <div class="stage-track">
              <div class="stage-fill" :style="{ width: stagePct(s.count) + '%' }" />
            </div>
            <span class="stage-count">{{ s.count }}</span>
          </div>
          <div v-if="!stats?.stage_counts?.some((s) => s.count)" class="muted">
            暂无进行中的投递
          </div>
        </el-card>
      </el-col>
      <el-col :span="14">
        <!-- 按岗位分组 -->
        <el-card shadow="never">
          <template #header>按岗位统计</template>
          <el-table :data="stats?.by_position || []" size="small" empty-text="暂无岗位">
            <el-table-column prop="position_name" label="岗位" min-width="160" />
            <el-table-column prop="pending" label="进行中" width="90" align="center" />
            <el-table-column prop="pass" label="已录用" width="90" align="center" />
            <el-table-column prop="fail" label="已淘汰" width="90" align="center" />
            <el-table-column prop="total" label="合计" width="80" align="center" />
          </el-table>
        </el-card>
      </el-col>
    </el-row>

    <!-- 阶段 × 岗位 交叉汇总表 -->
    <el-card shadow="never" style="margin-top: 14px">
      <template #header>
        <div class="card-header">
          <span>阶段 × 岗位汇总</span>
          <div class="matrix-tools">
            <el-radio-group v-model="matrixRange.range" size="small" @change="reloadAll">
              <el-radio-button v-for="r in RANGES" :key="r.value" :value="r.value">{{ r.label }}</el-radio-button>
            </el-radio-group>
            <template v-if="matrixRange.range === 'custom'">
              <el-date-picker v-model="matrixRange.start_date" type="date" placeholder="开始" value-format="YYYY-MM-DD" size="small" style="width: 130px" @change="reloadAll" />
              <span>至</span>
              <el-date-picker v-model="matrixRange.end_date" type="date" placeholder="结束" value-format="YYYY-MM-DD" size="small" style="width: 130px" @change="reloadAll" />
            </template>
            <el-button type="primary" size="small" :loading="exportingMatrix" @click="exportMatrix">
              <el-icon><Download /></el-icon>&nbsp;导出这张表
            </el-button>
          </div>
        </div>
      </template>

      <div class="matrix-hint">
        数字 = 所选时间范围内<b>通过了这一关</b>或<b>正停在这一关</b>的人数（在这一关被淘汰的不算）。
        「面试人数」= 通过专业面的（含后来过了 HR 面、终面的人）。<b>点数字可看具体是谁</b>。
      </div>

      <el-table :data="matrix?.rows || []" v-loading="matrixLoading" size="small" border empty-text="暂无数据">
        <el-table-column label="阶段" width="130" fixed>
          <template #default="{ row }">{{ row.label }}</template>
        </el-table-column>
        <el-table-column
          v-for="(p, i) in matrix?.positions || []"
          :key="p.id"
          :label="p.label"
          width="118"
          align="center"
        >
          <template #default="{ row }">
            <span v-if="row.cells[i] > 0" class="cell-num" @click="openCell(row.key, p.id)">{{ row.cells[i] }}</span>
            <span v-else class="zero">–</span>
          </template>
        </el-table-column>
        <el-table-column label="总计" width="80" align="center" fixed="right">
          <template #default="{ row }"><b>{{ row.total }}</b></template>
        </el-table-column>
      </el-table>

      <!-- 底部总计行 -->
      <div v-if="matrix?.positions?.length" class="matrix-total-row">
        <span class="mt-label">总计</span>
        <span v-for="(n, i) in matrix.col_totals" :key="i" class="mt-cell">{{ n }}</span>
        <span class="mt-cell mt-grand">{{ matrix.grand_total }}</span>
      </div>
    </el-card>

    <!-- 进行中的候选人所处阶段 -->
    <el-card shadow="never" style="margin-top: 14px">
      <template #header>
        <div class="card-header">
          <span>{{ matrix?.range_label || '本周' }}进行中的候选人所处阶段</span>
          <div class="matrix-tools">
            <span class="muted">阶段</span>
            <el-select
              v-model="pickedStages"
              multiple
              collapse-tags
              collapse-tags-tooltip
              placeholder="全部阶段"
              size="small"
              style="width: 240px"
            >
              <el-option v-for="o in STAGE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
            <span class="muted">共 {{ progress?.total || 0 }} 人</span>
            <el-button type="primary" size="small" :loading="exportingReport" @click="exportReport">
              <el-icon><Download /></el-icon>&nbsp;导出周报（两个表）
            </el-button>
          </div>
        </div>
      </template>

      <div class="matrix-hint">
        时间范围与上方交叉表一致。阶段可点开改写（如「待offer回传」「待入职 1.11」），改过的显示「手动」标记。
      </div>

      <el-table :data="progressRows" v-loading="progressLoading" size="small" border empty-text="该时间段内没有进行中的候选人">
        <el-table-column label="岗位" width="220">
          <template #default="{ row }">{{ row.position_label }}</template>
        </el-table-column>
        <el-table-column label="候选人" width="140">
          <template #default="{ row }">{{ row.name }}</template>
        </el-table-column>
        <el-table-column label="阶段" min-width="200">
          <template #default="{ row }">
            <!-- 编辑中：输入框 -->
            <template v-if="editingAppId === row.app_id">
              <el-input
                v-model="editingText"
                size="small"
                maxlength="50"
                placeholder="例：待offer回传"
                style="width: 260px"
                @keyup.enter="saveNote(row.app_id, editingText)"
              >
                <template #append>
                  <el-button :loading="savingNote" @click="saveNote(row.app_id, editingText)">存</el-button>
                </template>
              </el-input>
              <el-button link size="small" @click="cancelEdit">取消</el-button>
            </template>
            <!-- 非编辑：文案 + 手动标记 -->
            <template v-else>
              <span class="stage-text" @click="startEdit(row)">{{ row.stage_text }}</span>
              <el-tag v-if="row.is_custom" size="small" type="warning" effect="plain" style="margin-left: 6px">手动</el-tag>
              <el-button v-if="row.is_custom" link size="small" type="info" @click="saveNote(row.app_id, '')">恢复自动</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 点格子看名单 -->
    <el-dialog v-model="cellVisible" :title="cellData ? `${cellData.row_label} × ${cellData.position_label}（${cellData.count} 人）` : '明细'" width="640px">
      <el-table :data="cellData?.people || []" v-loading="cellLoading" border size="small" empty-text="这一格没有人">
        <el-table-column prop="name" label="姓名" width="130" />
        <el-table-column label="现在所处" min-width="130">
          <template #default="{ row }">
            <span>{{ row.stage_text }}</span>
            <el-tag v-if="row.is_custom" size="small" type="warning" effect="plain" style="margin-left: 6px">手动</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="本关情况" width="110" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="row.passed ? 'success' : 'warning'" effect="light">
              {{ row.passed ? '已通过' : '正等待' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="gotoApp(row.app_id)">查看</el-button>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="cellVisible = false">关闭</el-button>
      </template>
    </el-dialog>


    <!-- 导出面板 -->
    <el-card shadow="never" style="margin-top: 14px">
      <template #header>导出投递记录</template>

      <el-form label-width="80px">
        <el-form-item label="数据范围">
          <div class="filters">
            <el-date-picker v-model="exportForm.start_date" type="date" placeholder="开始日期" value-format="YYYY-MM-DD" style="width: 140px" />
            <span>至</span>
            <el-date-picker v-model="exportForm.end_date" type="date" placeholder="结束日期" value-format="YYYY-MM-DD" style="width: 140px" />
            <el-select v-model="exportForm.pos_id" placeholder="全部岗位" clearable style="width: 200px">
              <el-option v-for="p in positions" :key="p.id" :label="p.position_name" :value="p.id" />
            </el-select>
            <el-select v-model="exportForm.stage" placeholder="全部阶段" clearable style="width: 140px">
              <el-option v-for="s in STAGES" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-select v-model="exportForm.status" placeholder="全部状态" clearable style="width: 130px">
              <el-option v-for="s in STATUSES" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
          </div>
        </el-form-item>

        <el-form-item label="导出字段">
          <div class="fields-block">
            <div class="field-actions">
              <el-button link type="primary" size="small" @click="toggleAll">
                {{ allFields.length === fieldDefs.length ? '全不选' : '全选' }}
              </el-button>
              <span class="muted">已选 {{ allFields.length }} / {{ fieldDefs.length }} 列</span>
            </div>
            <div v-for="(fields, group) in groupedFields" :key="group" class="field-group">
              <div class="group-label">{{ GROUP[group] }}</div>
              <el-checkbox-group v-model="allFields">
                <el-checkbox v-for="f in fields" :key="f.key" :value="f.key" :label="f.label" />
              </el-checkbox-group>
            </div>
          </div>
        </el-form-item>

        <el-form-item label="文件格式">
          <el-radio-group v-model="exportForm.format">
            <el-radio value="xlsx">Excel（.xlsx）</el-radio>
            <el-radio value="csv">CSV（.csv，Excel 可直接打开）</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="exporting" @click="doExport">
            <el-icon><Download /></el-icon>&nbsp;导出
          </el-button>
          <span class="muted tip">只导出「投递」记录；导出的是当前筛选范围内的数据，行数会弹提示。</span>
        </el-form-item>
      </el-form>

      <el-alert type="info" :closable="false" show-icon title="按指定格式导出（模板对接）预留：等你提供标准 Excel 模板后实现，现在先用手选字段导出。" />
    </el-card>
  </div>
</template>

<style scoped>
.stat-cards {
  display: flex;
  gap: 14px;
  margin-bottom: 14px;
}
.stat-card {
  flex: 1; /* 每张平分整行宽度 */
  min-width: 0;
}
.stat-inner {
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-value {
  font-size: 26px;
  font-weight: 700;
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.stage-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.stage-name {
  width: 70px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}
.stage-track {
  flex: 1;
  height: 14px;
  background: var(--el-fill-color-light);
  border-radius: 7px;
  overflow: hidden;
}
.stage-fill {
  height: 100%;
  background: var(--el-color-primary);
  border-radius: 7px;
  transition: width 0.3s;
}
.stage-count {
  width: 24px;
  text-align: right;
  font-weight: 600;
}
.filters {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}
.fields-block {
  width: 100%;
}
.field-actions {
  margin-bottom: 8px;
}
.field-group {
  margin-bottom: 10px;
}
.group-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}
.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
/* 阶段 × 岗位汇总 */
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.matrix-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.matrix-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 10px;
}
.zero {
  color: var(--el-text-color-placeholder);
}
/* 交叉表格子里的数字：可点 */
.cell-num {
  cursor: pointer;
  color: var(--el-color-primary);
  border-bottom: 1px dashed var(--el-color-primary-light-5);
}
.cell-num:hover {
  font-weight: 600;
}
/* 阶段文案：可点，鼠标变成手型 */
.stage-text {
  cursor: pointer;
  border-bottom: 1px dashed var(--el-border-color);
}
.stage-text:hover {
  color: var(--el-color-primary);
}
.matrix-total-row {
  display: flex;
  align-items: center;
  margin-top: 8px;
  font-size: 13px;
  font-weight: 600;
  border-top: 1px dashed var(--el-border-color);
  padding-top: 8px;
}
.mt-label {
  width: 130px;
  flex: none;
  padding-left: 8px;
}
.mt-cell {
  width: 118px;
  flex: none;
  text-align: center;
}
.mt-grand {
  width: 80px;
  color: var(--el-color-primary);
}
.tip {
  margin-left: 12px;
}
</style>
