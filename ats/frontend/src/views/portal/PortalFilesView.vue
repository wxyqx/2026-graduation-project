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

// ---- Offer 文件回传：HR 发来的每一类，签署后按类型传回 ----
const RETURN_TYPES = [
  { value: 'offer_agreement', label: '签署的录用协议', hrCategory: 'offer_agreement' },
  { value: 'offer', label: '签署的 Offer', hrCategory: 'offer' },
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
  // 回传具有法律效力：签署件一经回传即视为正式提交，务必确认无误
  const typeName = RETURN_TYPES.find((t) => t.value === category)?.label || '其他附件'
  try {
    await ElMessageBox.confirm(
      `您即将回传「${file.name}」作为${typeName}。回传的文件具有法律效力，视为您已认真阅读并同意其全部内容，提交后不可自行撤回。请确认文件正确、已完成签署。`,
      '回传确认（重要）',
      { type: 'warning', confirmButtonText: '我已确认，回传', cancelButtonText: '再检查一下' },
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

const CATEGORY_LABEL = {
  resume: '简历',
  certificate: '证书',
  portfolio: '作品',
  offer: 'Offer',
  offer_agreement: '录用协议',
  background_check: '背景调查',
  other: '其他',
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

    <!-- Offer 文件回传：收到并签署后，按类型传回给 HR -->
    <section v-if="hasReturnTargets" class="portal-card">
      <h2 class="portal-section-title">Offer 文件回传</h2>
      <p class="portal-small" style="margin: 0 0 8px">
        收到录用协议 / Offer / 背景调查并签署后，点对应按钮回传给 HR；HR 端会标记「已回传」。
        <b>回传的文件具有法律效力，提交前请确认已认真阅读并完成签署。</b>
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
      title="简历由 HR 统一上传"
      type="info"
      show-icon
      :closable="false"
      description="如果简历需要更新，请联系 HR；你不需要自己上传。"
    />

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
            {{ CATEGORY_LABEL[file.category] || file.category }} · {{ sizeText(file.size_bytes) }} ·
            {{ fmtTime(file.upload_time) }}
          </div>
        </div>
        <el-button size="small" :loading="downloadingId === file.id" @click="download(file)">下载</el-button>
      </div>
    </section>
  </div>
</template>

<style scoped>
.file-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.return-group {
  padding: 10px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
}
.return-group:last-child {
  border-bottom: 0;
}
.return-app {
  font-weight: var(--ats-fw-medium);
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
  color: var(--el-text-color-regular);
}
</style>
