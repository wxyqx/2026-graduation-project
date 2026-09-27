<!--
  【汇总导出页】
  上半部分：统计卡 —— 数据来自 /stats/overview。
    5 张大数字卡 + 7 关人数分布条 + 按岗位分组小表
  下半部分：导出面板 —— 选范围 → 勾字段 → 选格式 → 导出 xlsx/csv 下载。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { exportFields, exportFile, positionApi, settingsApi, statsApi } from '../api'
import { STAGES, STAGE_COLOR, STAGE_LABEL, STATUSES } from '../constants'
import { downloadBlob } from '../utils/download'

const route = useRoute()
const router = useRouter()
const refreshStats = inject('refreshStats')

// 阶段多选（用于「进行中名单」筛选）：初始值优先取网址参数（?stages=ai,test），否则默认全选
const STAGE_OPTIONS = STAGES.map((s) => ({ value: s.value, label: s.label }))
function stagesFromQuery() {
  const q = route.query.stages
  if (typeof q !== 'string' || !q) return null
  const picked = q.split(',').filter((s) => STAGES.some((x) => x.value === s))
  return picked.length ? picked : null
}
const pickedStages = ref(stagesFromQuery() || STAGES.map((s) => s.value))
// 阶段勾选一变就重新取名单（用 watch：手动选和程序改都生效）
watch(pickedStages, () => loadProgress(), { deep: true })

// 名单里「本关情况」的三种状态
const STATE_META = {
  passed: { text: '已通过', type: 'success' },
  waiting: { text: '正等待', type: 'warning' },
  rejected: { text: '已淘汰', type: 'danger' },
}

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

// 关键数字：从「5 张同构卡片」改成一行紧凑指标，把版面让给下面的漏斗
const statCards = computed(() => {
  const s = stats.value
  if (!s) return []
  return [
    { label: '在招岗位', value: s.position_count },
    { label: '进行中', value: s.pending_count },
    { label: '已录用', value: s.pass_count, tone: 'ok' },
    { label: '已淘汰', value: s.fail_count, tone: 'bad' },
    { label: '本月录用', value: s.month_hired },
  ]
})

// 漏斗：按 7 关给出「走到这一关及以后」的人数，逐关收窄，深浅即进度
// 数据源是 /stats/overview 的 stage_counts（当前停在某一关的人数），
// 从最后一关往前累加，得到「至少走到这一关」的人数
const funnel = computed(() => {
  const list = stats.value?.stage_counts || []
  if (!list.length) return []
  const out = []
  let acc = 0
  for (let i = list.length - 1; i >= 0; i -= 1) {
    acc += list[i].count
    out.unshift({ ...list[i], reached: acc })
  }
  const top = out[0]?.reached || 1
  return out.map((x, i) => ({ ...x, index: i, pct: Math.round((x.reached / top) * 100) }))
})

// ---- 阶段 × 岗位 交叉汇总表（周报那种表）----
const RANGES = [
  { value: 'week', label: '本周' },
  { value: 'last_week', label: '上周' },
  { value: 'month', label: '本月' },
  { value: 'all', label: '全部' },
  { value: 'custom', label: '自定义' },
]
// 时间范围：初始值也优先取网址参数（?range=month&start=&end=），刷新/收藏能还原
const matrixRange = reactive({
  range:
    typeof route.query.range === 'string' && RANGES.some((r) => r.value === route.query.range)
      ? route.query.range
      : 'week',
  start_date: typeof route.query.start === 'string' ? route.query.start : null,
  end_date: typeof route.query.end === 'string' ? route.query.end : null,
})
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

// 筛选变了就同步进网址（replace 不新增历史）：刷新、收藏、分享都能还原同一视图。
// 只同步真正影响数据的筛选：时间范围与阶段多选。
// 不同步：导出面板的日期（与时间范围重复）、字段勾选（数组冗长，属展示偏好）。
function queryKey(q) {
  return Object.keys(q)
    .sort()
    .map((k) => `${k}=${q[k]}`)
    .join('&')
}
watch(
  [matrixRange, pickedStages],
  () => {
    const query = {}
    // week 是默认值，不写进网址，保持地址干净
    if (matrixRange.range !== 'week') query.range = matrixRange.range
    if (matrixRange.range === 'custom') {
      if (matrixRange.start_date) query.start = matrixRange.start_date
      if (matrixRange.end_date) query.end = matrixRange.end_date
    }
    // 全选等同于不筛，同样不写
    if (pickedStages.value.length && pickedStages.value.length < STAGES.length) {
      query.stages = pickedStages.value.join(',')
    }
    if (queryKey(query) !== queryKey(route.query)) router.replace({ query })
  },
  { deep: true },
)

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

    <!-- 关键数字：一行紧凑指标（不再是 5 张同构卡片） -->
    <div class="metrics">
      <div v-for="c in statCards" :key="c.label" class="metric" :class="c.tone ? `is-${c.tone}` : ''">
        <span class="metric-value">{{ c.value }}</span>
        <span class="metric-label">{{ c.label }}</span>
      </div>
    </div>

    <div class="top-grid">
      <!-- 漏斗：整个汇总页的首页元素，一眼看出堵在哪一关 -->
      <section class="panel funnel-panel">
        <h3>招聘漏斗</h3>
        <p class="funnel-note muted">每条的人数 = 走到这一关及以后的人（越往下越窄，窄得快的那一关就是堵点）</p>
        <div v-for="f in funnel" :key="f.stage" class="funnel-row">
          <span class="funnel-name">{{ f.label }}</span>
          <div class="funnel-track">
            <div
              class="funnel-fill"
              :style="{ transform: `scaleX(${Math.max(f.pct, 2) / 100})`, background: STAGE_COLOR[f.stage] }"
            />
          </div>
          <span class="funnel-count">
            <b>{{ f.reached }}</b>
            <span class="funnel-now" :title="`当前正停在这一关：${f.count} 人`">＋{{ f.count }}</span>
          </span>
        </div>
        <div v-if="!funnel.some((f) => f.reached)" class="muted">暂无进行中的投递</div>
      </section>

      <section class="panel">
        <h3>按岗位统计</h3>
        <el-table :data="stats?.by_position || []" size="small" empty-text="暂无岗位">
          <el-table-column prop="position_name" label="岗位" min-width="150" show-overflow-tooltip />
          <el-table-column label="进行中" width="82" align="right">
            <template #default="{ row }"><span class="ats-nums">{{ row.pending }}</span></template>
          </el-table-column>
          <el-table-column label="已录用" width="82" align="right">
            <template #default="{ row }"><span class="ats-nums">{{ row.pass }}</span></template>
          </el-table-column>
          <el-table-column label="已淘汰" width="82" align="right">
            <template #default="{ row }"><span class="ats-nums">{{ row.fail }}</span></template>
          </el-table-column>
          <el-table-column label="合计" width="72" align="right">
            <template #default="{ row }"><b class="ats-nums">{{ row.total }}</b></template>
          </el-table-column>
        </el-table>
      </section>
    </div>

    <!-- 阶段 × 岗位 交叉汇总表 -->
    <section class="panel" style="margin-top: var(--ats-sp-4)">
      <div class="card-header">
        <h3>阶段 × 岗位汇总</h3>
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

      <div class="matrix-hint">
        数字 = 所选时间范围内<b>通过了这一关</b>或<b>正停在这一关</b>的人数（在这一关被淘汰的不算）。
        「面试人数」= 专业面 / HR面 / 终面 <b>任一关</b>在范围内的人数，<b>面过即计入（含被淘汰的）</b>。
        <b>点数字可看具体是谁</b>。
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
            <button
              v-if="row.cells[i] > 0"
              type="button"
              class="cell-num"
              :aria-label="`查看 ${row.label} × ${p.label} 的 ${row.cells[i]} 人`"
              @click="openCell(row.key, p.id)"
            >
              {{ row.cells[i] }}
            </button>
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
    </section>

    <!-- 进行中的候选人所处阶段 -->
    <section class="panel" style="margin-top: var(--ats-sp-4)">
      <div class="card-header">
        <h3>{{ matrix?.range_label || '本周' }}进行中的候选人所处阶段</h3>
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

      <div class="matrix-hint">
        时间范围与上方交叉表一致。阶段可点开改写（如「待offer回传」「待入职 1.11」），改过的显示「手动」标记。
      </div>

      <el-table :data="progressRows" v-loading="progressLoading" size="small" border class="ats-vlist" empty-text="该时间段内没有进行中的候选人">
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
              <button
                type="button"
                class="stage-text"
                :aria-label="`修改「${row.name}」的阶段文案（当前：${row.stage_text}）`"
                @click="startEdit(row)"
              >
                {{ row.stage_text }}
              </button>
              <el-tag v-if="row.is_custom" size="small" type="warning" effect="plain" style="margin-left: 6px">手动</el-tag>
              <el-button v-if="row.is_custom" link size="small" type="info" @click="saveNote(row.app_id, '')">恢复自动</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 点格子看名单 -->
    <el-dialog v-model="cellVisible" class="ats-dialog-wide" :title="cellData ? `${cellData.row_label} × ${cellData.position_label}（${cellData.count} 人）` : '明细'">
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
            <el-tag size="small" :type="STATE_META[row.state]?.type || 'warning'" effect="light">
              {{ STATE_META[row.state]?.text || '—' }}
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
    <section class="panel" style="margin-top: var(--ats-sp-4)">
      <h3>导出投递记录</h3>

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
    </section>
  </div>
</template>

<style scoped>
/* ---- 关键数字：一行紧凑指标 ---- */
.metrics {
  display: flex;
  gap: var(--ats-sp-6);
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-3) var(--ats-sp-4);
  margin-bottom: var(--ats-sp-4);
}
.metric {
  display: flex;
  align-items: baseline;
  gap: var(--ats-sp-2);
}
.metric-value {
  font-size: var(--ats-fs-stat);
  font-weight: var(--ats-fw-bold);
  font-variant-numeric: var(--ats-nums);
  line-height: 1.1;
  color: var(--el-text-color-primary);
}
.metric-label {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.metric.is-ok .metric-value {
  color: var(--el-color-success);
}
.metric.is-bad .metric-value {
  color: var(--el-color-danger);
}

/* ---- 顶部分栏：漏斗在左（更宽，它是主视觉）、按岗位统计在右 ---- */
.top-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: var(--ats-sp-4);
  margin-bottom: var(--ats-sp-4);
}
.panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-4);
}
.panel h3 {
  margin: 0 0 var(--ats-sp-3);
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
}
.funnel-note {
  margin: -8px 0 var(--ats-sp-3);
}

/* ---- 漏斗 ---- */
.funnel-row {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
  margin-bottom: 6px;
}
.funnel-name {
  width: 68px;
  flex: none;
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-regular);
}
.funnel-track {
  flex: 1;
  height: 16px;
  background: var(--ats-track);
  border-radius: 3px;
  overflow: hidden;
}
/* 色条长度 = 到达人数占比；颜色按关卡加深，收窄本身就是信息。
   宽度固定 100%，用 scaleX 表达占比：只动 transform，走合成层，不触发布局 */
.funnel-fill {
  height: 100%;
  width: 100%;
  border-radius: 3px;
  transform-origin: left center;
  transition: transform 0.3s;
}
.funnel-count {
  width: 74px;
  flex: none;
  text-align: right;
  font-size: var(--ats-fs-note);
}
.funnel-count b {
  font-variant-numeric: var(--ats-nums);
  font-size: var(--ats-fs-body);
}
/* 「当前正停在这一关」的人数，用浅色副标区分于累计值 */
.funnel-now {
  margin-left: 4px;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
  font-variant-numeric: var(--ats-nums);
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
/* 阶段 × 岗位汇总 */
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
/* 交叉表格子里的数字：可点。用 button 承载，键盘也能到达 */
.cell-num {
  padding: 0;
  background: none;
  font: inherit;
  cursor: pointer;
  color: var(--el-color-primary);
  border: 0;
  border-bottom: 1px dashed var(--el-color-primary-light-5);
}
.cell-num:hover {
  font-weight: 600;
}
/* 阶段文案：可点，鼠标变成手型。同样改成 button，键盘可聚焦 */
.stage-text {
  padding: 0;
  background: none;
  font: inherit;
  text-align: left;
  cursor: pointer;
  color: inherit;
  border: 0;
  border-bottom: 1px dashed var(--el-border-color);
}
.stage-text:hover {
  color: var(--el-color-primary);
}
/* 去掉默认 outline 前先给出等效的可见焦点圈 */
.cell-num:focus-visible,
.stage-text:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
  border-radius: 2px;
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
