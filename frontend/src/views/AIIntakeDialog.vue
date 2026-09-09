<!--
  【AI 录入简历弹窗】投递列表页右上角「AI 录入简历」打开。
    上半：拖拽/选择 PDF（可多个），或点「＋加一份粘贴文本」用纯文本兜底（扫描件抠不出字时用）
    下半：点「开始 AI 录入」→ loading → 每一份简历一条结果（识别出谁、投哪个岗位、通过与否、理由）
    结果里 status 含义：ok 成功建档 / duplicate 已投过 / no_position 没匹配到岗位 / extract_failed 文字提取失败 / error AI 出错
    关闭弹窗后由父组件负责刷新列表和顶部统计。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'

import { uploadIntake } from '../api'

// props：父组件打开弹窗时要传进来
defineProps({
  visible: { type: Boolean, default: false }, // 控制弹窗开关
})
const emit = defineEmits(['close']) // 关闭时通知父组件（父组件去刷新列表）

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

async function submit() {
  const files = fileList.value.map((f) => f.raw)
  const texts = textItems.map((x) => x.text.trim()).filter((t) => t)
  if (!files.length && !texts.length) return

  running.value = true
  results.value = null
  summary.value = null
  try {
    const data = await uploadIntake(files, texts)
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
    width="720px"
    destroy-on-close
    :close-on-click-modal="false"
    @close="close"
  >
    <p class="intro">
      上传 PDF 简历，AI 自动识别姓名、匹配在招岗位并按岗位要求初筛、建档。PDF 与提取文本都不保存，
      只留判断结果。需先在「系统设置」添加并启用至少一个 AI 接口。
    </p>

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
.muted {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
