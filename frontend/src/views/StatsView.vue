<!--
  【汇总导出页】
  上半部分：统计卡 —— 数据来自 /stats/overview。
    5 张大数字卡 + 8 关人数分布条 + 按岗位分组小表
  下半部分：导出面板 —— 选范围 → 勾字段 → 选格式 → 导出 xlsx/csv 下载。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, inject, onMounted, reactive, ref } from 'vue'

import { exportFields, exportFile, positionApi, statsApi } from '../api'
import { STAGES, STAGE_LABEL, STATUSES } from '../constants'
import { downloadBlob } from '../utils/download'

const refreshStats = inject('refreshStats')

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

    <!-- 统计卡 -->
    <el-row :gutter="14" class="stat-cards">
      <el-col v-for="c in statCards" :key="c.label" :span="24 / 5">
        <el-card shadow="never" class="stat-card">
          <div class="stat-inner">
            <el-icon :size="30" :style="{ color: c.color }"><component :is="c.icon" /></el-icon>
            <div>
              <div class="stat-value">{{ c.value }}</div>
              <div class="stat-label">{{ c.label }}</div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

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
  margin-bottom: 14px;
}
.stat-card {
  margin-bottom: 14px;
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
.tip {
  margin-left: 12px;
}
</style>
