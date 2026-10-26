<script setup>
import { onMounted, ref, computed } from 'vue'

import PortalFormsList from '../../components/PortalFormsList.vue'
import { portalFileApi } from '../../api/portal'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fmtTime } from '../../utils/format'

const files = ref([])
const loading = ref(true)
const downloadingId = ref(null)
const returningType = ref('')
const returnInput = ref(null)

// ---- Offer 文件回传：签署件（录用协议 / 背景调查）与 Offer 要求的附件，都按类型传回 ----
// offer 本身无需签署，候选人传的是 Offer 里要求提交的文件；其余两类是签署件，走法律效力确认话术
const RETURN_TYPES = [
  { value: 'offer_agreement', label: '签署的录用协议', hrCategory: 'offer_agreement' },
  { value: 'offer', label: 'Offer 附件', hrCategory: 'offer' },
  { value: 'background_check', label: '签署的背景调查', hrCategory: 'background_check' },
]
const returnTargets = computed(() => {
  const sent = files.value.filter(
    (f) => f.application_id && ['offer_agreement', 'offer', 'background_check'].includes(f.category) && f.uploaded_by_role === 'hr',
  )
  // 按投递分组：每条投递 × 每个类型一行
  const apps = [...new Set(sent.map((f) => f.application_id))]
  return apps.map((appId) => ({
    applicationId: appId,
    label: `投递 #${appId}`,
    types: RETURN_TYPES.map((t) => {
      const hrFile = sent.find((f) => f.application_id === appId && f.category === t.hrCategory)
      const returned = files.value
        .filter((f) => f.application_id === appId && f.category === t.hrCategory && f.uploaded_by_role === 'candidate')
        .sort((a, b) => new Date(b.upload_time) - new Date(a.upload_time))[0]
      return { ...t, hrFile, returned: returned || null }
    }),
  }))
})
const hasReturnTargets = computed(() => returnTargets.value.some((r) => r.types.some((t) => t.hrFile)))

function pickReturn(applicationId, category) {
  returningType.value = `${applicationId}:${category}`
  returnInput.value?.click()
}

async function onReturnPicked(e) {
  const file = e.target.files?.[0]
  const key = returningType.value
  e.target.value = ''
  if (!file || !key) return
  const [appId, category] = key.split(':')
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.warning('文件不能超过 10MB')
    return
  }
  // 签署件语气放缓（v3.17 P1-8）：提示正式性与可撤回，不再宣称"不可撤回/法律效力"
  const typeName = RETURN_TYPES.find((t) => t.value === category)?.label || '其他附件'
  const needSign = category === 'offer_agreement' || category === 'background_check'
  try {
    await ElMessageBox.confirm(
      needSign
        ? `您即将回传「${file.name}」作为${typeName}。回传视为您已认真阅读并同意其全部内容的正式提交，请确认文件正确、已完成签署；传错可在本页撤回后重传。`
        : `您即将回传「${file.name}」作为${typeName}。请确认文件与 Offer 中的要求一致；传错可在本页撤回后重传。`,
      needSign ? '回传确认（重要）' : '回传确认',
      { type: 'warning', confirmButtonText: needSign ? '我已确认，回传' : '确认回传', cancelButtonText: '再检查一下' },
    )
  } catch {
    return
  }
  returningType.value = key
  try {
    await portalFileApi.uploadReturn(file, category, Number(appId))
    ElMessage.success('已回传，HR 端会看到「已回传」标记')
    await load()
  } finally {
    returningType.value = ''
  }
}

// ---- 文件预览：PDF / 图片直接在弹窗里看（简历、HR 发来的 Offer、自己回传的都可以）----
const preview = ref({ visible: false, name: '', url: '', type: 'other' })
async function previewFile(file) {
  const res = await portalFileApi.blob(file)
  const mime = res.headers['content-type'] || file.mime_type || ''
  preview.value = {
    visible: true,
    name: file.original_name,
    url: URL.createObjectURL(res.data),
    type: mime.includes('pdf') ? 'pdf' : mime.startsWith('image/') ? 'image' : 'other',
  }
}
function previewClose() {
  if (preview.value.url) URL.revokeObjectURL(preview.value.url)
  preview.value = { visible: false, name: '', url: '', type: 'other' }
}

const CATEGORY_LABEL = {
  resume: '简历',
  certificate: '证书',
  portfolio: '作品',
  offer: 'Offer',
  offer_agreement: '录用协议',
  background_check: '背景调查',
  other: '其他',
}

// HR 发来的 Offer 类文件：文件名常看不出来是什么，类型提为彩色标签，并写明下一步动作
const OFFER_TAG = { offer_agreement: 'warning', offer: 'success', background_check: 'primary' }
const OFFER_HINT = {
  offer_agreement: 'HR 发来的录用协议：下载签署后，到上方「Offer 文件回传」处回传',
  offer: 'HR 发来的 Offer：无需签署；其中要求提交的文件，到上方「Offer 文件回传」处回传',
  background_check: 'HR 发来的背景调查：下载签署后，到上方「Offer 文件回传」处回传',
}
const isHrOfferFile = (file) =>
  file.uploaded_by_role === 'hr' && ['offer', 'offer_agreement', 'background_check'].includes(file.category)

// 我上传的、还没被 HR 转正的新版简历（P1-7：待确认可撤回）
const isMyPendingResume = (file) =>
  file.uploaded_by_role === 'candidate' && file.category === 'resume' && !file.is_current
// 我回传的文件（P1-8：可撤回重传）
const isMyReturn = (file) => file.uploaded_by_role === 'candidate' && file.category !== 'resume'

const resumeUploading = ref(false)
const myResumeInput = ref(null)
function pickMyResume() {
  myResumeInput.value?.click()
}
async function onMyResumePicked(e) {
  const f = e.target.files?.[0]
  e.target.value = ''
  if (!f) return
  if (f.size > 10 * 1024 * 1024) {
    ElMessage.warning('文件不能超过 10MB')
    return
  }
  resumeUploading.value = true
  try {
    await portalFileApi.uploadResume(f)
    ElMessage.success('新版简历已上传，HR 核对转正前可随时撤回')
    await load()
  } finally {
    resumeUploading.value = false
  }
}

async function removeMine(file) {
  const isResume = isMyPendingResume(file)
  try {
    await ElMessageBox.confirm(
      isResume
        ? `撤回你上传的「${file.original_name}」？撤回后 HR 将看不到这份新简历。`
        : `撤回你回传的「${file.original_name}」？HR 端将不再显示这份回传件，撤回后可重新回传。`,
      '撤回确认',
      { type: 'warning', confirmButtonText: '撤回', cancelButtonText: '再想想' },
    )
  } catch {
    return
  }
  if (isResume) await portalFileApi.removeResume(file.id)
  else await portalFileApi.removeReturn(file.id)
  ElMessage.success('已撤回')
  await load()
}

function sizeText(bytes) {
  if (!bytes && bytes !== 0) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  loading.value = true
  try {
    files.value = await portalFileApi.list()
  } finally {
    loading.value = false
  }
}

async function download(file) {
  downloadingId.value = file.id
  try {
    await portalFileApi.download(file)
  } finally {
    downloadingId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div class="portal-page">
    <div class="portal-page-head">
      <div>
        <h1>文件 / 表单</h1>
        <div class="portal-page-sub">点表单直接进填写页；简历由 HR 上传</div>
      </div>
    </div>

    <PortalFormsList />

    <!-- Offer 文件回传：签署件与 Offer 要求的附件，都按类型传回给 HR -->
    <section v-if="hasReturnTargets" class="portal-card">
      <h2 class="portal-section-title">Offer 文件回传</h2>
      <p class="portal-small" style="margin: 0 0 8px">
        收到录用协议 / 背景调查并完成签署后，点对应按钮回传给 HR；HR 端会标记「已回传」。
        Offer 无需签署，Offer 中要求提交的文件也从「Offer 附件」处回传。
        <b>签署件回传视为正式提交，提交前请确认已完成签署；传错可在本页撤回后重传。</b>
      </p>
      <input ref="returnInput" type="file" hidden @change="onReturnPicked" />
      <div v-for="appGroup in returnTargets" :key="appGroup.applicationId" class="return-group">
        <div class="return-app">{{ appGroup.label }}</div>
        <div v-for="t in appGroup.types" :key="t.value" class="return-row">
          <template v-if="t.hrFile">
            <span class="return-label">{{ t.label }}</span>
            <template v-if="t.returned">
              <el-tag size="small" type="success" effect="plain">已回传</el-tag>
              <span class="portal-small">{{ t.returned.original_name }} · {{ fmtTime(t.returned.upload_time) }}</span>
              <el-button size="small" link type="primary" @click="previewFile(t.returned)">预览</el-button>
              <el-button size="small" link type="primary" :loading="returningType === `${appGroup.applicationId}:${t.value}`" @click="pickReturn(appGroup.applicationId, t.value)">
                重新上传
              </el-button>
            </template>
            <el-button
              v-else
              size="small"
              type="primary"
              plain
              :loading="returningType === `${appGroup.applicationId}:${t.value}`"
              @click="pickReturn(appGroup.applicationId, t.value)"
            >
              回传{{ t.label.replace('签署的', '') }}
            </el-button>
          </template>
        </div>
        <div class="return-row">
          <span class="return-label">其他附件</span>
          <el-button size="small" plain :loading="returningType === `${appGroup.applicationId}:other`" @click="pickReturn(appGroup.applicationId, 'other')">
            回传附件
          </el-button>
        </div>
      </div>
    </section>

    <el-alert
      title="简历更新：可自助上传，HR 确认后生效"
      type="info"
      show-icon
      :closable="false"
      description="HR 上传的简历仍然只读；如果你需要更新简历，点下方按钮上传新版，HR 核对转正前可随时撤回。"
    />
    <div class="portal-card" style="margin-top: 12px">
      <el-button type="primary" plain :loading="resumeUploading" @click="pickMyResume">
        {{ resumeUploading ? '上传中…' : '上传新版简历' }}
      </el-button>
      <input ref="myResumeInput" type="file" hidden accept=".pdf,.doc,.docx,.jpg,.jpeg,.png" @change="onMyResumePicked" />
      <span class="portal-small" style="margin-left: 10px">上传后 HR 会收到并核对，转正前不影响你的投递</span>
    </div>

    <div v-if="loading" class="portal-card"><el-skeleton :rows="4" animated /></div>

    <div v-else-if="!files.length" class="portal-empty">
      <el-icon><Document /></el-icon>
      <p>HR 还没有上传你的简历</p>
      <span class="portal-small">上传后会显示在这里；没有简历暂时不能投递</span>
    </div>

    <section v-else class="portal-card">
      <h2 class="portal-section-title">文件</h2>
      <div v-for="file in files" :key="file.id" class="file-row">
        <div class="file-icon"><el-icon><Document /></el-icon></div>
        <div class="file-main">
          <div class="file-name">{{ file.original_name }}</div>
          <div class="file-meta">
            <el-tag v-if="file.category === 'resume' && file.is_current" size="small" type="success" effect="plain">当前简历</el-tag>
            <el-tag v-else-if="isMyPendingResume(file)" size="small" type="warning" effect="plain">我上传的新版简历（待 HR 确认）</el-tag>
            <el-tag v-else-if="isHrOfferFile(file)" size="small" :type="OFFER_TAG[file.category]" effect="light">
              {{ CATEGORY_LABEL[file.category] }}（HR 发来）
            </el-tag>
            <template v-else>{{ CATEGORY_LABEL[file.category] || file.category }}</template>
            · {{ sizeText(file.size_bytes) }} ·
            {{ fmtTime(file.upload_time) }}
          </div>
          <div v-if="isHrOfferFile(file)" class="portal-small file-hint">{{ OFFER_HINT[file.category] }}</div>
        </div>
        <el-button size="small" :loading="downloadingId === file.id" @click="download(file)">下载</el-button>
        <el-button size="small" @click="previewFile(file)">预览</el-button>
        <el-button v-if="isMyPendingResume(file) || isMyReturn(file)" size="small" type="danger" plain @click="removeMine(file)">
          撤回
        </el-button>
      </div>
    </section>

    <!-- 文件预览：所见即所下载（PDF 翻页 / 图片直显，其他格式提示下载） -->
    <el-dialog v-model="preview.visible" :title="`预览：${preview.name}`" width="860px" append-to-body destroy-on-close @close="previewClose">
      <iframe v-if="preview.type === 'pdf'" :src="preview.url" class="file-preview-frame" :title="preview.name" />
      <img v-else-if="preview.type === 'image'" :src="preview.url" class="file-preview-img" :alt="preview.name" />
      <div v-else class="file-preview-fallback">
        <p>该文件格式不支持在线预览</p>
        <el-button type="primary" @click="previewClose">知道了，直接下载</el-button>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 层次：区标题加粗；法律效力提醒用警示色从灰色小说明里跳出来 */
.portal-section-title {
  font-weight: var(--ats-fw-bold);
}
.portal-card p.portal-small b {
  color: var(--el-color-danger);
  font-size: var(--ats-fs-note);
}

.file-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
/* 文件名是列表主体，加中字重和灰色元信息拉开 */
.file-main :deep(.file-name) {
  font-weight: var(--ats-fw-medium);
}
.file-hint {
  margin-top: 3px;
}

.return-group {
  padding: 10px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.return-group:last-child {
  border-bottom: 0;
}
.return-app {
  font-size: var(--ats-fs-body);
  font-weight: var(--ats-fw-bold);
  color: var(--el-text-color-primary);
  margin-bottom: 4px;
}
.return-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 4px 0;
}
.return-label {
  width: 110px;
  flex: none;
  font-weight: var(--ats-fw-bold);
  color: var(--el-text-color-primary);
}

/* 文件预览弹窗：PDF 铺满、图片居中 */
.file-preview-frame {
  display: block;
  width: 100%;
  height: 70vh;
  border: 0;
}
.file-preview-img {
  display: block;
  max-width: 100%;
  margin: 0 auto;
}
.file-preview-fallback {
  padding: 48px 16px;
  text-align: center;
  color: var(--el-text-color-secondary);
}
.file-preview-fallback p {
  margin: 0 0 12px;
}
</style>
