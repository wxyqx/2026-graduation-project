<!--
  【AI 录入简历弹窗】投递列表页右上角「AI 录入简历」打开。
    上半：拖拽/选择 PDF（可多个），或点「＋加一份粘贴文本」用纯文本兜底（扫描件抠不出字时用）
    下半：点「开始 AI 录入」→ loading → 每一份简历一条结果（识别出谁、投哪个岗位、通过与否、理由）
    结果里 status 含义：ok 成功建档 / duplicate 已投过 / no_position 没匹配到岗位 / extract_failed 文字提取失败 / error AI 出错
    关闭弹窗后由父组件负责刷新列表和顶部统计。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { positionApi, uploadIntake } from '../api'
import { positionExtras } from '../stores/positionExtras'

// props：父组件打开弹窗时要传进来
defineProps({
  visible: { type: Boolean, default: false }, // 控制弹窗开关
})
const emit = defineEmits(['close']) // 关闭时通知父组件（父组件去刷新列表）

// ---- 岗位选择：整批简历都按这个岗位筛；选「自动识别」则让 AI 判断 ----
const AUTO = 0 // 用 0 代表「自动识别」，因为岗位编号从 1 开始，不会冲突
const positions = ref([])
const posId = ref(AUTO)

async function loadPositions() {
  try {
    positions.value = await positionApi.list()
  } catch {
    /* 拦截器已提示 */
  }
}
onMounted(loadPositions)

// 选中的是不是自动模式
const isAuto = computed(() => posId.value === AUTO)
// 当前选中岗位的名字（用于提交前提示）
const selectedName = computed(() => {
  if (isAuto.value) return '自动识别'
  return positions.value.find((p) => p.id === posId.value)?.position_name || ''
})

// ---- 文件收集（el-upload 只当选择器用，不自动上传）----
const uploadRef = ref()
const fileList = ref([])
const MAX_SIZE = 20 * 1024 * 1024

function beforeAdd(raw) {
  if (!raw.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.warning(`「${raw.name}」不是 PDF，已跳过`)
    return false
  }
  if (raw.size > MAX_SIZE) {
    ElMessage.warning(`「${raw.name}」超过 20MB，已跳过`)
    return false
  }
  return true
}

// ---- 粘贴文本条目 ----
const textItems = reactive([{ id: 1, text: '' }])
let textSeq = 1
function addTextItem() {
  textItems.push({ id: ++textSeq, text: '' })
}
function removeTextItem(item) {
  const idx = textItems.findIndex((x) => x.id === item.id)
  if (idx >= 0) textItems.splice(idx, 1)
}

// ---- 提交与结果 ----
const running = ref(false)
const results = ref(null) // 后端返回的 results 数组
const summary = ref(null)

// 一份都没有就禁用按钮
const nothingToSubmit = computed(() => fileList.value.length === 0 && textItems.every((x) => !x.text.trim()))

// 有几个岗位设置了「AI 附加条件」（来自浏览器 localStorage）
const extraCount = computed(() => Object.keys(positionExtras.all()).length)

async function submit() {
  const files = fileList.value.map((f) => f.raw)
  const texts = textItems.map((x) => x.text.trim()).filter((t) => t)
  if (!files.length && !texts.length) return
  if (!positions.value.length) {
    ElMessage.warning('系统里还没有岗位，请先到「岗位管理」新建一个')
    return
  }

  running.value = true
  results.value = null
  summary.value = null
  try {
    // 带上各岗位在浏览器里存的「AI 附加条件」；posId 非自动时指定岗位
    const data = await uploadIntake(files, texts, positionExtras.all(), isAuto.value ? null : posId.value)
    results.value = data.results
    summary.value = data.summary
    if (data.summary?.ok > 0) ElMessage.success(`AI 录入完成：成功建档 ${data.summary.ok} 条`)
  } catch {
    // 后端拒绝（无岗位 / 无启用配置…）时拦截器已弹中文提示
  } finally {
    running.value = false
  }
}

function reset() {
  results.value = null
  summary.value = null
  textItems.splice(1)
  textItems[0].text = ''
  uploadRef.value?.clearFiles()
  fileList.value = []
}

// status → 标签配色与中文
const STATUS_META = {
  ok: { type: 'success', text: '成功建档' },
  duplicate: { type: 'info', text: '重复投递' },
  no_position: { type: 'warning', text: '未匹配岗位' },
  extract_failed: { type: 'warning', text: '提取失败' },
  error: { type: 'danger', text: '出错' },
}

function close() {
  emit('close')
  reset()
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="AI 录入简历"
    class="ats-dialog-wide"
    destroy-on-close
    :close-on-click-modal="false"
    @close="close"
  >
    <p class="intro">
      上传 PDF 简历，AI 识别候选人姓名、按所选岗位的要求初筛并建档。PDF 与提取文本都不保存，
      只留判断结果。需先在「系统设置」添加并启用至少一个 AI 接口。
    </p>

    <!-- 应聘岗位：整批简历都按这里选的岗位筛 -->
    <div class="pos-row">
      <span class="pos-label">应聘岗位</span>
      <el-select v-model="posId" style="flex: 1">
        <el-option :value="0" label="自动识别（由 AI 判断投递岗位）" />
        <el-option
          v-for="p in positions"
          :key="p.id"
          :value="p.id"
          :label="p.owner ? `${p.position_name}　—　${p.owner}` : p.position_name"
        />
      </el-select>
    </div>
    <div class="pos-hint" :class="{ warn: isAuto }">
      <template v-if="isAuto">
        AI 会自己从在招岗位里挑一个；挑不出来就不建档。岗位特殊（或有两三个同名岗位）时，建议手动指定。
      </template>
      <template v-else>
        本次上传的简历都按「{{ selectedName }}」筛选：AI 只判断是否符合这个岗位，不会挑别的岗位。
      </template>
    </div>

    <el-alert
      v-if="extraCount > 0"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 12px"
      :title="`已启用 ${extraCount} 个岗位的「AI 附加条件」，本次筛选中会作为额外限制一并发给 AI`"
    />

    <div class="upload-zone">
      <el-upload
        ref="uploadRef"
        drag
        multiple
        accept=".pdf"
        :auto-upload="false"
        :before-upload="beforeAdd"
        :file-list="fileList"
        :on-change="(f, list) => (fileList = list)"
        :on-remove="(f, list) => (fileList = list)"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">把 PDF 拖到这里，或 <em>点击选择</em>（可多选）</div>
        <template #tip>
          <div class="el-upload__tip">仅支持 PDF，单个不超过 20MB；扫描件（图片型）请改用下方粘贴文本</div>
        </template>
      </el-upload>
    </div>

    <div class="text-section">
      <div class="text-head">
        <span class="muted">粘贴纯文本兜底（每格一份简历）</span>
        <el-button link type="primary" size="small" @click="addTextItem">＋ 加一份文本</el-button>
      </div>
      <div v-for="item in textItems" :key="item.id" class="text-row">
        <el-input
          v-model="item.text"
          type="textarea"
          :rows="2"
          placeholder="把简历文字整个粘贴进来（至少 30 字）"
        />
        <el-button v-if="textItems.length > 1" text type="danger" @click="removeTextItem(item)">
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>

    <div class="action-row">
      <el-button @click="reset">清空</el-button>
      <el-button type="primary" :loading="running" :disabled="nothingToSubmit" @click="submit">
        开始 AI 录入
      </el-button>
    </div>

    <!-- 逐条结果 -->
    <template v-if="results">
      <el-alert
        type="success"
        :closable="false"
        :title="`共 ${results.length} 份：成功 ${summary?.ok || 0}、重复 ${summary?.duplicate || 0}、未匹配 ${summary?.no_position || 0}、提取失败 ${summary?.extract_failed || 0}、出错 ${summary?.error || 0}`"
        style="margin-bottom: 10px"
      />
      <el-table :data="results" size="small" max-height="300" border>
        <el-table-column label="简历" width="150">
          <template #default="{ row }">{{ row.filename || `文本#${row.index + 1}` }}</template>
        </el-table-column>
        <el-table-column label="候选人" width="110">
          <template #default="{ row }">{{ row.candidate_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="匹配岗位" min-width="140">
          <template #default="{ row }">{{ row.position_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="结果" width="110">
          <template #default="{ row }">
            <el-tag :type="STATUS_META[row.status]?.type" size="small">
              {{ row.status === 'ok' ? (row.ai_result === 'pass' ? '通过' : '淘汰') : STATUS_META[row.status]?.text }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="说明 / 理由" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.message || row.ai_comment || '' }}</template>
        </el-table-column>
      </el-table>
    </template>

    <template #footer>
      <el-button type="primary" @click="close">关 闭</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.intro {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
/* 岗位选择行 */
.pos-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
}
.pos-label {
  font-size: 14px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}
.pos-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.7;
  margin: 0 0 12px 60px;
}
.pos-hint.warn {
  color: var(--el-color-warning);
}
.upload-zone {
  margin-bottom: 14px;
}
.text-section {
  margin-bottom: 12px;
}
.text-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}
.text-row {
  display: flex;
  gap: 6px;
  margin-bottom: 6px;
  align-items: flex-start;
}
.action-row {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-bottom: 8px;
}
</style>
