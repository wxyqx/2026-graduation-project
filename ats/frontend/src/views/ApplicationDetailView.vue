<!--
  【投递详情页】一条投递的全貌。

  设计说明（v3.12）：这一页的主体是「7 关管线」，不再是几张并列的信息卡。
    · 候选人 / 岗位信息压缩成顶部一条信息带，把版面让给管线
    · 管线是页面主角：每关一个节点，连接线按进度染色；已过的关实心带对勾，
      当前关加光晕并标「进行中」，被淘汰的关整节点标红
    · 结果与时间拆成两个元素显示，不再用「通过 · 2026-09-15 13:34」这种中点拼接
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, inject, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { applicationApi, candidateApi, formTemplateApi, interviewApi } from '../api'
import { auth } from '../stores/auth'
import PortalFormRenderer from '../components/PortalFormRenderer.vue'
import RichTextEditor from '../components/RichTextEditor.vue'
import { RESULT_LABEL, STAGE_COLOR, STAGE_LABEL, STATUS_LABEL, STATUS_TYPE, stageHasEvaluation } from '../constants'
import { fmtTime } from '../utils/format'

const route = useRoute()
const router = useRouter()
const refreshStats = inject('refreshStats')

const app = ref(null)
const candidate = ref(null)
const files = ref([])
const submissions = ref([])
const loading = ref(false)
const downloadingId = ref(null)

const SOURCE_LABEL = { admin: 'HR 手动', ai_intake: 'AI 录入', portal: '候选人投递' }

async function load() {
  loading.value = true
  try {
    const detail = await applicationApi.detail(route.params.id)
    app.value = detail
    if (detail.candidate?.id) {
      const [cand, fileList, appForms, candForms] = await Promise.all([
        candidateApi.detail(detail.candidate.id),
        candidateApi.files(detail.candidate.id),
        applicationApi.forms(detail.id),
        candidateApi.forms(detail.candidate.id),
      ])
      candidate.value = cand
      files.value = fileList
      // 本次投递的岗位答卷 + 个人资料表（application_id 为 null 的那些）
      const merged = [...appForms, ...candForms.filter((s) => s.application_id === null)]
      const seen = new Set()
      submissions.value = merged.filter((s) => (seen.has(s.id) ? false : seen.add(s.id)))
    }
  } finally {
    loading.value = false
  }
}
onMounted(load)

async function downloadFile(file) {
  downloadingId.value = file.id
  try {
    await candidateApi.downloadFile(file)
  } finally {
    downloadingId.value = null
  }
}

function submissionAnswers(sub) {
  const out = {}
  for (const item of sub.items || []) out[item.field_key] = item.value
  return out
}

const templateFieldsCache = new Map()
const formFieldsBySub = ref(new Map())

async function loadTemplateFields(templateId) {
  if (templateFieldsCache.has(templateId)) return templateFieldsCache.get(templateId)
  const detail = await formTemplateApi.detail(templateId)
  const fields = (detail.fields || []).filter((f) => f.is_active !== false)
  templateFieldsCache.set(templateId, fields)
  return fields
}

async function ensureFormFields(subs) {
  const next = new Map()
  for (const sub of subs) {
    try {
      next.set(sub.id, await loadTemplateFields(sub.template_id))
    } catch {
      next.set(sub.id, [])
    }
  }
  formFieldsBySub.value = next
}

watch(submissions, (val) => {
  if (val && val.length) ensureFormFields(val)
  else formFieldsBySub.value = new Map()
}, { immediate: true })



const FILE_CATEGORY = { resume: '简历', certificate: '证书', portfolio: '作品', other: '其他' }
const FORM_STATUS = { draft: '草稿', submitted: '已提交' }

// 当前简历：个人信息页签第一行展示 + 下载
const currentResume = computed(() => files.value.find((f) => f.category === 'resume' && f.is_current) || null)

// 附件材料：除三类 Offer 文件之外的全部上传（候选人传的 + HR 传的）；Offer 文件单独在「Offer 文件」页签管理
const attachmentFiles = computed(() =>
  files.value.filter((f) => !['offer', 'offer_agreement', 'background_check'].includes(f.category)),
)

// ---- Offer 文件：录用协议 / Offer / 背景调查三类，上传→预览→发送后才对候选人可见 ----
const OFFER_TYPES = [
  { value: 'offer_agreement', label: '录用协议', tag: 'warning' },
  { value: 'offer', label: 'Offer', tag: 'success' },
  { value: 'background_check', label: '背景调查', tag: 'primary' },
]
const OFFER_CATEGORIES = OFFER_TYPES.map((t) => t.value)
const offerLabel = (category) => OFFER_TYPES.find((t) => t.value === category)?.label || category
const offerTag = (category) => OFFER_TYPES.find((t) => t.value === category)?.tag || 'info'

const offerFiles = computed(() =>
  files.value.filter((f) => OFFER_CATEGORIES.includes(f.category) && f.application_id === app.value?.id),
)
// 候选人回传：同一类型取最新一次上传（历史版本保留）
const returnFor = (category) =>
  offerFiles.value
    .filter((f) => f.category === category && f.uploaded_by_role === 'candidate')
    .sort((a, b) => new Date(b.upload_time) - new Date(a.upload_time))[0] || null
const offerUploading = ref('')
const offerInput = ref(null)

function pickOfferFile(category) {
  offerInput.value?.click()
  offerInput.value.dataset.category = category
}

async function onOfferPicked(e) {
  const file = e.target.files?.[0]
  const category = e.target.dataset.category || 'offer'
  e.target.value = ''
  if (!file || !app.value) return
  offerUploading.value = category
  try {
    await candidateApi.uploadFile(app.value.candidate.id, file, category, app.value.id)
    ElMessage.success(`「${offerLabel(category)}」已上传，预览检查后点「发送」才会对候选人可见`)
    await load()
  } finally {
    offerUploading.value = ''
  }
}

// 预览：PDF / 图片在线看，其他格式提示下载
const preview = ref({ visible: false, name: '', url: '', type: 'other' })

async function previewOfferFile(file) {
  downloadingId.value = file.id
  try {
    const resp = await candidateApi.fileBlob(file.id)
    const mime = resp.headers['content-type'] || file.mime_type || ''
    const type = mime.includes('pdf') ? 'pdf' : mime.startsWith('image/') ? 'image' : 'other'
    preview.value = {
      visible: true,
      name: file.original_name,
      url: URL.createObjectURL(resp.data),
      type,
    }
  } finally {
    downloadingId.value = null
  }
}

function previewClose() {
  if (preview.value.url) URL.revokeObjectURL(preview.value.url)
  preview.value = { visible: false, name: '', url: '', type: 'other' }
}

// 发送：预览确认后才对候选人可见；重复发送幂等（不覆盖首次发送时间）
async function sendOfferFile(file) {
  try {
    await ElMessageBox.confirm(
      `发送「${file.original_name}」给候选人？发送后候选人端「文件」页立即可下载，发送时间不可更改。`,
      '发送确认',
      { type: 'warning', confirmButtonText: '发送', cancelButtonText: '再看看' },
    )
  } catch {
    return
  }
  await candidateApi.sendOfferFile(file.id)
  ElMessage.success('已发送，候选人端可见')
  await load()
}

async function removeOfferFile(file) {
  try {
    await ElMessageBox.confirm(`删除「${file.original_name}」？候选人端将不再显示。`, '删除文件', { type: 'warning' })
  } catch {
    return
  }
  await candidateApi.removeFile(file.id)
  ElMessage.success('已删除')
  await load()
}

// 学历 / 招聘类型的固定选项（HR 从简历摘录时直接选）
const DEGREE_OPTIONS = ['大专', '本科', '硕士', '博士', '其他']
const HIRE_TYPE_OPTIONS = ['校招', '社招']

function sizeText(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

// 返回列表：能用浏览器后退就用后退（带着原来的筛选条件回去）；
// 直接打开这个网址（没有上一页）就退回投递列表首页
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'applications' })
}

const activeIndex = computed(() => {
  if (!app.value) return 0
  return app.value.stages.findIndex((s) => s.stage === app.value.current_stage)
})

// 每一关在管线上的形态
function nodeState(s, i) {
  if (s.result === 'fail') return 'rejected'
  if (s.result === 'pass') return 'passed'
  if (i === activeIndex.value) return app.value?.overall_status === 'pass' ? 'passed' : 'current'
  return 'upcoming'
}

const isPending = computed(() => app.value?.overall_status === 'pending')
const canRevert = computed(() => app.value && !(app.value.current_stage === 'ai' && isPending.value))

async function advance(result) {
  if (result === 'fail') {
    try {
      await ElMessageBox.confirm(
      `确定淘汰「${app.value.candidate_name}」？淘汰后将立即发送淘汰通知，候选人的账号会在 2 天后注销（期间登录可见通知，之后无法登录）。`,
      '淘汰确认',
      { type: 'warning', confirmButtonText: '确认淘汰', cancelButtonText: '再想想' },
    )
    } catch {
      return
    }
  }
  await applicationApi.advance(app.value.id, app.value.current_stage, result, result === 'fail')
  ElMessage.success(result === 'pass' ? '已通过本阶段' : '已标记淘汰')
  await load()
  refreshStats?.()
}

async function revert() {
  try {
    await ElMessageBox.confirm('撤回上一步操作？', '撤回确认', { type: 'warning' })
  } catch {
    return
  }
  await applicationApi.revert(app.value.id)
  ElMessage.success('已撤回')
  await load()
  refreshStats?.()
}

// ---- 个人信息就地编辑（姓名/电话/邮箱/备注）----
const RESUME_FIELDS = ['onboard_date', 'school', 'degree', 'major', 'expected_salary', 'work_location', 'hire_type', 'work_experience']
const profileForm = reactive({ name: '', phone: '', email: '', remark: '', ...Object.fromEntries(RESUME_FIELDS.map((f) => [f, ''])) })
const profileSaving = ref(false)
const profileDirty = computed(() => {
  const c = candidate.value || {}
  const same = (a, b) => (a || '') === (b || '')
  return (
    !same(profileForm.name, c.name) ||
    !same(profileForm.phone, c.phone) ||
    !same(profileForm.email, c.email) ||
    !same(profileForm.remark, c.remark) ||
    RESUME_FIELDS.some((f) => !same(profileForm[f], c[f]))
  )
})

watch([candidate, app], () => {
  const c = candidate.value || app.value?.candidate || {}
  profileForm.name = c.name || ''
  profileForm.phone = c.phone || ''
  profileForm.email = c.email || ''
  profileForm.remark = c.remark || ''
  for (const f of RESUME_FIELDS) profileForm[f] = c[f] || ''
}, { immediate: true })

async function saveProfile() {
  const cur = candidate.value || app.value?.candidate
  if (!cur) return
  if (!profileForm.name.trim()) {
    ElMessage.warning('姓名不能为空')
    return
  }
  profileSaving.value = true
  const payload = {
    name: profileForm.name.trim(),
    phone: profileForm.phone.trim(),
    email: profileForm.email.trim(),
    remark: profileForm.remark,
    ...Object.fromEntries(RESUME_FIELDS.map((f) => [f, profileForm[f].trim()])),
  }
  try {
    try {
      await candidateApi.update(cur.id, payload)
    } catch (e) {
      // 409 = 姓名或手机号与已有候选人冲突：确认后带 confirm_duplicate 重新提交
      if (e.response?.status === 409) {
        await ElMessageBox.confirm(e.response.data?.detail || e.detail || '与已有候选人冲突，确定继续吗？', '冲突提示', {
          type: 'warning',
          confirmButtonText: '仍要保存',
          cancelButtonText: '取消',
        })
        await candidateApi.update(cur.id, { ...payload, confirm_duplicate: true })
      } else {
        throw e
      }
    }
    ElMessage.success('个人信息已更新')
    await load()
    refreshStats?.()
  } finally {
    profileSaving.value = false
  }
}

// ---- 编辑权限：候选人负责人=全部关卡；阶段负责人=本关；无主的关=可编辑（编辑即认领）----
const meId = computed(() => auth.user.value?.id ?? null)
function stageOwnerId(stage) {
  return app.value?.stage_owners?.[stage]?.user_id ?? null
}
function stageOwnerName(stage) {
  return app.value?.stage_owners?.[stage]?.name || null
}
function canEditStage(stage) {
  const me = meId.value
  if (me == null || !app.value) return true
  if (app.value.candidate_owner_id === me) return true
  const sid = stageOwnerId(stage)
  return sid == null || sid === me
}
const selectedStageEditable = computed(() => canEditStage(selectedNote.value?.stage))
const currentStageEditable = computed(() => canEditStage(app.value?.current_stage))

// ---- 各关记录（就地编辑：选关后直接在页内填原因 / 面试评价）----
// 列出「已出结果的人工关」+「正在进行中的当前关」——进行中也能先写（面试完就记评价，之后再定通过/淘汰）。
// ai 关不在此列，它有独立面板，理由由 AI 生成、不可手改。
const noteStages = computed(() =>
  (app.value?.stages || []).filter((s) => s.stage !== 'ai' && (s.result || s.is_current)),
)

// 详情页标签页：默认看各关记录；支持 ?tab=notices 等直达（投递列表的「通知×N」标记点进来）
const activeTab = ref(route.query.tab ? String(route.query.tab) : 'notes')

// 各关记录：进度条滑动选关，下方只展示选中关的记录
const noteIndex = ref(0)
const selectedNote = computed(() => noteStages.value[noteIndex.value] || null)

const noteMarks = computed(() => {
  const marks = {}
  noteStages.value.forEach((s, i) => {
    // 滑块标签下带本关负责人：每个阶段都能看到这关归谁管（未认领的显示「未认领」）
    const owner = stageOwnerName(s.stage)
    marks[i] = {
      style: {
        color: s.stage === selectedNote.value?.stage ? 'var(--el-color-primary)' : STAGE_COLOR[s.stage],
        fontWeight: s.stage === selectedNote.value?.stage ? 'var(--ats-fw-bold)' : 'var(--ats-fw-normal)',
        whiteSpace: 'nowrap',
      },
      label: owner ? `${s.label}·${owner}` : s.label,
    }
  })
  return marks
})

watch(noteStages, (list) => {
  if (!list.length) {
    noteIndex.value = 0
    return
  }
  // 选中的关还在就保持；不在了（刷新/撤回）跳到正在进行的当前关，没有就第一项
  const cur = selectedNote.value?.stage
  const kept = list.findIndex((s) => s.stage === cur)
  if (kept >= 0) noteIndex.value = kept
  else noteIndex.value = Math.max(0, list.findIndex((s) => s.is_current))
}, { immediate: true })

// 就地表单：切关时同步，保存走 stage-note 接口
const noteForm = reactive({ reason: '', evaluation: '' })
const noteResult = ref('')
const noteSaving = ref(false)
const noteHasEvaluation = computed(() => stageHasEvaluation(selectedNote.value?.stage))
const noteReasonPlaceholder = computed(() => {
  if (selectedNote.value?.result === 'fail') return '写清楚这一关为什么淘汰，例如：学历不符 / 笔试分数偏低 / 团队匹配度不足……'
  if (selectedNote.value?.result === 'pass') return '写清楚这一关为什么通过，例如：本科+3 年相关经验，符合岗位要求……'
  return '这一关还在进行中，可先记评估要点或面试反馈，之后再决定通过 / 淘汰。'
})

watch(selectedNote, (s) => {
  noteForm.reason = s?.reason || ''
  noteForm.evaluation = s?.evaluation || ''
  noteResult.value = s?.result || ''
}, { immediate: true })

// 结果只有「正在进行的当前关」能改（走推进/淘汰流程）；历史关的结果只能靠「撤回」，这里锁住
const noteResultEditable = computed(
  () => app.value && isPending.value && selectedNote.value?.stage === app.value.current_stage,
)

async function onNoteResultChange(v) {
  if (!v) {
    // 选回「进行中」没有对应操作，恢复原值
    noteResult.value = selectedNote.value?.result || ''
    return
  }
  if (v === 'fail') {
    try {
      await ElMessageBox.confirm(
      `确定淘汰「${app.value.candidate_name}」？淘汰后将立即发送淘汰通知，候选人的账号会在 2 天后注销（期间登录可见通知，之后无法登录）。`,
      '淘汰确认',
      { type: 'warning', confirmButtonText: '确认淘汰', cancelButtonText: '再想想' },
    )
    } catch {
      noteResult.value = selectedNote.value?.result || ''
      return
    }
  }
  try {
    await applicationApi.advance(app.value.id, app.value.current_stage, v, v === 'fail')
    ElMessage.success(v === 'pass' ? '已通过本阶段' : '已标记淘汰')
    await load()
    refreshStats?.()
  } catch {
    noteResult.value = selectedNote.value?.result || ''
  }
}

async function saveNoteInline() {
  if (!selectedNote.value) return
  noteSaving.value = true
  try {
    await applicationApi.saveStageNote(app.value.id, selectedNote.value.stage, noteForm.reason, noteForm.evaluation)
    ElMessage.success('记录已保存')
    await load()
  } finally {
    noteSaving.value = false
  }
}

// ---- 候选人通知：通过关卡生成草稿，这里逐人编辑后发送 ----
const STAGE_LABELS_LOCAL = { phone: '电话沟通', test: '笔试', pro: '专业面', hr: 'HR面', final: '终面', onboard: '入职', eliminated: '淘汰' }
const appNoticesList = ref([])
const noticeEdit = ref(null) // { id, title, body }
const noticeBusy = ref(false)

async function loadAppNotices() {
  if (!app.value) return
  try {
    appNoticesList.value = await applicationApi.appNotices(app.value.id)
  } catch {
    appNoticesList.value = []
  }
}

function startNoticeEdit(n) {
  noticeEdit.value = { id: n.id, title: n.title, body: n.body || '' }
}

async function saveNoticeEdit() {
  const e = noticeEdit.value
  if (!e) return
  if (!e.title.trim()) {
    ElMessage.warning('通知标题不能为空')
    return
  }
  noticeBusy.value = true
  try {
    await applicationApi.editAppNotice(app.value.id, e.id, { title: e.title.trim(), body: e.body })
    noticeEdit.value = null
    ElMessage.success('已保存')
    await loadAppNotices()
  } finally {
    noticeBusy.value = false
  }
}

// 发送前预览：弹窗里就是候选人弹窗的样子，标题/正文可以直接改，改完即发送
const sendPreview = ref(null) // { id, title, body, stage }

// 预览时间与候选人端显示一致（toLocaleString 本地化格式）
const sendPreviewTime = computed(() => new Date().toLocaleString())

function openSendPreview(n) {
  // 边界：候选人没有手机号 = 没开通候选人端账号，通知发出去也没人能收到，直接提示失败
  const phone = candidate.value?.phone || app.value?.candidate?.phone
  if (!phone) {
    ElMessage.error('发送失败：该候选人没有手机号，未开通候选人端账号；请先补上手机号，再重试发送')
    return
  }
  let body = n.body || ''
  // 通知正文没有文件清单时，自动附上这次投递的 Offer 文件清单（与后端发送时兜底一致）
  if (offerFiles.value.length && !body.includes('offer-file-list')) {
    const rows = offerFiles.value
      .map((f) => `<li>${offerLabel(f.category)}：${f.original_name}</li>`)
      .join('')
    body += `<div class="offer-file-list"><b>随通知附上以下文件</b>（请到「文件」页下载填写）：<ul>${rows}</ul></div>`
  }
  sendPreview.value = { id: n.id, title: n.title, body, stage: n.stage }
}

async function confirmSendPreview() {
  const sp = sendPreview.value
  if (!sp) return
  if (!sp.title.trim()) {
    ElMessage.warning('通知标题不能为空')
    return
  }
  noticeBusy.value = true
  try {
    // 先保存改动，再发送（幂等）
    await applicationApi.editAppNotice(app.value.id, sp.id, { title: sp.title.trim(), body: sp.body })
    await applicationApi.sendAppNotice(app.value.id, sp.id)
    ElMessage.success('已发送，候选人登录即弹窗可见')
    sendPreview.value = null
    noticeEdit.value = null
    await loadAppNotices()
  } finally {
    noticeBusy.value = false
  }
}

async function discardNotice(n) {
  try {
    await ElMessageBox.confirm('放弃这条草稿？（不发送，删除后不可恢复）', '放弃草稿', { type: 'warning' })
  } catch {
    return
  }
  noticeBusy.value = true
  try {
    await applicationApi.discardAppNotice(app.value.id, n.id)
    ElMessage.success('已放弃')
    if (noticeEdit.value?.id === n.id) noticeEdit.value = null
    await loadAppNotices()
  } finally {
    noticeBusy.value = false
  }
}

watch(app, (v) => v && loadAppNotices(), { immediate: false })

// ---- 面试评价 AI 生成：贴逐字稿 → 复用面试评价功能起草 ----
const aiOpen = ref(false)
const transcript = ref('')
const aiRunning = ref(false)
const configUsed = ref('')
const transcriptLen = computed(() => transcript.value.length)
const canGenerate = computed(() => transcript.value.trim().length >= 30 && transcript.value.length <= 30000 && !aiRunning.value)

async function generateEvaluation() {
  aiRunning.value = true
  configUsed.value = ''
  try {
    const data = await interviewApi.evaluate(transcript.value)
    noteForm.evaluation = data.text
    configUsed.value = data.config_used
    ElMessage.success('已生成，可自行修改后再保存')
  } catch {
    /* 拦截器已弹中文提示 */
  } finally {
    aiRunning.value = false
  }
}
</script>

<template>
  <div v-loading="loading">
    <div class="page-header">
      <div class="title-row">
        <el-button link @click="goBack">
          <el-icon><ArrowLeft /></el-icon>&nbsp;返回列表
        </el-button>
        <h2 v-if="app">{{ app.candidate?.name }}</h2>
        <el-tag v-if="app" :type="STATUS_TYPE[app.overall_status]" size="small" effect="light">
          {{ STATUS_LABEL[app.overall_status] }}
        </el-tag>
        <span v-if="app" class="muted">{{ app.position?.position_name }}</span>
      </div>
      <div v-if="app">
        <el-tag size="small" effect="plain" class="stage-owner-tag" title="当前关的负责人 HR（首次编辑该关的 HR 自动认领）">
          {{ STAGE_LABEL[app.current_stage] }}负责人：{{ stageOwnerName(app.current_stage) || '未认领' }}
        </el-tag>
        <el-button
          type="primary"
          :disabled="!isPending || !currentStageEditable"
          :title="currentStageEditable ? '' : '本阶段由其他 HR 负责，你只能查看'"
          @click="advance('pass')"
        >
          通过「{{ STAGE_LABEL[app.current_stage] }}」
        </el-button>
        <el-button
          type="danger"
          plain
          :disabled="!isPending || !currentStageEditable"
          :title="currentStageEditable ? '' : '本阶段由其他 HR 负责，你只能查看'"
          @click="advance('fail')"
        >淘汰</el-button>
        <el-button :disabled="!canRevert" @click="revert">撤回</el-button>
      </div>
    </div>

    <template v-if="app">
      <!-- 信息带：候选人 + 岗位压缩成一行，版面让给管线 -->
      <div class="meta-band">
        <div class="meta-item">
          <span class="meta-label">姓名</span>
          <span class="meta-value">{{ app.candidate?.name }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">负责人</span>
          <span class="meta-value">{{ app.candidate_owner_name || '暂无' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">来源</span>
          <span class="meta-value">
            <el-tag
              size="small"
              effect="plain"
              :type="app.source === 'portal' ? 'success' : app.source === 'ai_intake' ? 'warning' : 'info'"
            >
              {{ SOURCE_LABEL[app.source] || app.source || 'HR 手动' }}
            </el-tag>
          </span>
        </div>
        <div class="meta-item">
          <span class="meta-label">手机号</span>
          <span class="meta-value ats-nums">{{ candidate?.phone || app.candidate?.phone || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">账号</span>
          <span class="meta-value">
            <el-tag :type="candidate?.has_account ? 'success' : 'info'" size="small" effect="plain">
              {{ candidate?.has_account ? '已开通' : '未开通' }}
            </el-tag>
          </span>
        </div>
        <div class="meta-item">
          <span class="meta-label">备注</span>
          <span class="meta-value">{{ app.candidate?.remark || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">负责人</span>
          <span class="meta-value">{{ app.position?.owner || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">录入时间</span>
          <span class="meta-value ats-nums">{{ fmtTime(app.candidate?.create_time) }}</span>
        </div>
      </div>

      <!-- 管线：本页主体 -->
      <section class="panel">
        <div class="panel-head">
          <h3>招聘流程</h3>
          <span class="muted">当前在「{{ STAGE_LABEL[app.current_stage] }}」</span>
        </div>

        <ol class="pipeline">
          <li
            v-for="(s, i) in app.stages"
            :key="s.stage"
            class="node"
            :class="`is-${nodeState(s, i)}`"
          >
            <span class="node-dot" :style="{ background: STAGE_COLOR[s.stage] }">
              <el-icon v-if="s.result === 'pass'"><Select /></el-icon>
              <el-icon v-else-if="s.result === 'fail'"><CloseBold /></el-icon>
            </span>
            <span class="node-name">{{ s.label }}</span>
            <span v-if="s.result" class="node-result" :class="s.result">{{ RESULT_LABEL[s.result] }}</span>
            <span v-else-if="s.is_current && isPending" class="node-result current">进行中</span>
            <span v-if="s.time" class="node-time ats-nums">{{ fmtTime(s.time) }}</span>
          </li>
        </ol>

        <!-- AI 筛选：它就是管线第一关的说明，并进同一块面板 -->
        <div class="ai-band">
          <span class="ai-label">AI 筛选</span>
          <template v-if="app.ai_result">
            <el-tag :type="app.ai_result === 'pass' ? 'success' : 'danger'" size="small" effect="light">
              {{ RESULT_LABEL[app.ai_result] }}
            </el-tag>
            <span class="ai-comment">{{ app.ai_comment || '（AI 未给出理由）' }}</span>
          </template>
          <span v-else class="muted">尚未进行 AI 筛选。手动通过第一关即视为人工代替 AI 筛选。</span>
        </div>
      </section>

      <!-- 下方内容收进标签页：页面不再无限往下滚 -->
      <el-tabs v-model="activeTab" class="detail-tabs">
        <el-tab-pane label="个人信息" name="profile">
          <el-descriptions :column="3" border class="profile-desc">
            <el-descriptions-item label="简历" :span="3">
              <template v-if="currentResume">
                <span class="resume-name">{{ currentResume.original_name }}</span>
                <el-button link type="primary" :loading="downloadingId === currentResume.id" @click="downloadFile(currentResume)">
                  下载
                </el-button>
              </template>
              <span v-else class="muted">还没有上传简历</span>
            </el-descriptions-item>
            <el-descriptions-item label="姓名">
              <el-input v-model="profileForm.name" placeholder="候选人姓名" maxlength="50" />
            </el-descriptions-item>
            <el-descriptions-item label="电话">
              <el-input v-model="profileForm.phone" placeholder="11 位手机号" maxlength="11" inputmode="tel" />
            </el-descriptions-item>
            <el-descriptions-item label="邮箱">
              <el-input v-model="profileForm.email" placeholder="选填" maxlength="100" />
            </el-descriptions-item>
            <!-- HR 从简历摘录的个人信息：与候选人填写的表单答卷是两套数据，各自独立 -->
            <el-descriptions-item label="到岗时间">
              <el-date-picker
                v-model="profileForm.onboard_date"
                type="date"
                value-format="YYYY-MM-DD"
                :editable="false"
                placeholder="选择到岗日期"
                style="width: 100%"
              />
            </el-descriptions-item>
            <el-descriptions-item label="毕业院校">
              <el-input v-model="profileForm.school" placeholder="如 天津理工大学" maxlength="100" />
            </el-descriptions-item>
            <el-descriptions-item label="学历">
              <el-select v-model="profileForm.degree" clearable placeholder="选择学历" style="width: 100%">
                <el-option v-for="d in DEGREE_OPTIONS" :key="d" :label="d" :value="d" />
              </el-select>
            </el-descriptions-item>
            <el-descriptions-item label="专业">
              <el-input v-model="profileForm.major" placeholder="如 计算机科学与技术" maxlength="100" />
            </el-descriptions-item>
            <el-descriptions-item label="期望薪资">
              <el-input v-model="profileForm.expected_salary" placeholder="如 20k×16" maxlength="50" />
            </el-descriptions-item>
            <el-descriptions-item label="工作地点">
              <el-input v-model="profileForm.work_location" placeholder="期望工作地点" maxlength="100" />
            </el-descriptions-item>
            <el-descriptions-item label="类型">
              <el-select v-model="profileForm.hire_type" clearable placeholder="校招 / 社招" style="width: 100%">
                <el-option v-for="t in HIRE_TYPE_OPTIONS" :key="t" :label="t" :value="t" />
              </el-select>
            </el-descriptions-item>
            <el-descriptions-item label="工作经历" :span="3">
              <el-input v-model="profileForm.work_experience" type="textarea" :autosize="{ minRows: 3 }" placeholder="从简历摘录的工作经历，按「公司 / 时间 / 职责 / 业绩」填写" />
            </el-descriptions-item>
            <el-descriptions-item label="来源">{{ SOURCE_LABEL[app.source] || app.source || '—' }}</el-descriptions-item>
            <el-descriptions-item label="账号">{{ candidate?.has_account ? '已开通' : '未开通' }}</el-descriptions-item>
            <el-descriptions-item label="负责人">{{ app.position?.owner || '—' }}</el-descriptions-item>
            <el-descriptions-item label="录入时间" :span="2">{{ fmtTime(app.candidate?.create_time) }}</el-descriptions-item>
            <el-descriptions-item label="备注" :span="3">
              <el-input v-model="profileForm.remark" type="textarea" :rows="2" placeholder="如：内推 / 已电话确认到岗时间……" maxlength="500" show-word-limit />
            </el-descriptions-item>
          </el-descriptions>
          <div class="profile-actions">
            <el-button type="primary" :loading="profileSaving" :disabled="!profileDirty" @click="saveProfile">
              保存修改
            </el-button>
          </div>
        </el-tab-pane>

        <el-tab-pane label="附件材料" name="files">
          <div class="panel-head">
            <span class="muted">HR 上传，候选人只读</span>
          </div>
          <el-table class="rounded-table" :data="attachmentFiles" border size="small" empty-text="还没有上传简历或附件">
            <el-table-column prop="original_name" label="文件名" min-width="200" show-overflow-tooltip />
            <el-table-column label="分类" width="80">
              <template #default="{ row }">{{ FILE_CATEGORY[row.category] || row.category }}</template>
            </el-table-column>
            <el-table-column label="大小" width="90">
              <template #default="{ row }">{{ sizeText(row.size_bytes) }}</template>
            </el-table-column>
            <el-table-column label="版本" width="100">
              <template #default="{ row }">
                <template v-if="row.category === 'resume'">
                  <el-tag v-if="row.is_current" size="small" type="success" effect="plain">当前简历</el-tag>
                  <span v-else class="muted">历史</span>
                </template>
                <span v-else class="muted">—</span>
              </template>
            </el-table-column>
            <el-table-column label="上传时间" width="150">
              <template #default="{ row }">{{ fmtTime(row.upload_time) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="80" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :loading="downloadingId === row.id" @click="downloadFile(row)">
                  下载
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>

        <!-- 每份答卷一个标签：面试登记表 / 职业底色图 / 个人资料表… -->
        <el-tab-pane
          v-for="sub in submissions"
          :key="sub.id"
          :label="sub.template_name"
          :name="`form-${sub.id}`"
          lazy
        >
          <div class="panel-head">
            <span class="muted">
              <el-tag size="small" :type="sub.status === 'submitted' ? 'success' : 'info'" effect="plain">
                {{ FORM_STATUS[sub.status] || sub.status }}
              </el-tag>
              &nbsp;v{{ sub.template_version }} · {{ fmtTime(sub.submit_time || sub.update_time) }}
            </span>
          </div>
          <div class="submission-answers">
            <PortalFormRenderer
              :fields="formFieldsBySub.get(sub.id) || []"
              :model-value="submissionAnswers(sub)"
              :disabled="true"
            />
          </div>
        </el-tab-pane>

        <!-- Offer 文件：发给候选人下载填写的文档 -->
        <el-tab-pane :label="`Offer 文件${offerFiles.length ? `（${offerFiles.length}）` : ''}`" name="offer" lazy>
          <div class="panel-head">
            <span class="muted">
              先上传、预览检查；然后到「候选人通知」页签把通知（会自动列明这些文件）发送出去，候选人才能看到
            </span>
            <span class="offer-upload-btns">
              <el-button
                v-for="t in OFFER_TYPES"
                :key="t.value"
                type="primary"
                plain
                :loading="offerUploading === t.value"
                @click="pickOfferFile(t.value)"
              >
                上传{{ t.label }}
              </el-button>
            </span>
            <input ref="offerInput" type="file" hidden @change="onOfferPicked" />
          </div>
          <el-table
            v-if="offerFiles.length"
            class="rounded-table"
            :data="offerFiles"
            border
            size="small"
            style="margin-top: var(--ats-sp-3)"
          >
            <el-table-column prop="original_name" label="文件名" min-width="200" show-overflow-tooltip />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small" effect="plain" :type="offerTag(row.category)">{{ offerLabel(row.category) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="大小" width="80">
              <template #default="{ row }">{{ sizeText(row.size_bytes) }}</template>
            </el-table-column>
            <el-table-column label="上传时间" width="150">
              <template #default="{ row }">{{ fmtTime(row.upload_time) }}</template>
            </el-table-column>
            <el-table-column label="候选人回传" min-width="200">
              <template #default="{ row }">
                <template v-if="row.uploaded_by_role === 'candidate'">
                  <el-tag size="small" type="success" effect="plain">本行即候选人回传件</el-tag>
                </template>
                <template v-else-if="returnFor(row.category)">
                  <el-tag size="small" type="success" effect="plain">已回传</el-tag>
                  <span class="muted send-time">{{ returnFor(row.category).original_name }}</span>
                  <el-button link type="primary" :loading="downloadingId === returnFor(row.category).id" @click="downloadFile(returnFor(row.category))">
                    下载
                  </el-button>
                </template>
                <span v-else class="muted">未回传</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" :loading="downloadingId === row.id" @click="previewOfferFile(row)">预览</el-button>
                <el-button link type="primary" @click="downloadFile(row)">下载</el-button>
                <el-button link type="danger" @click="removeOfferFile(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty v-else description="还没有上传 Offer 文件" :image-size="72" />
        </el-tab-pane>

        <!-- 候选人通知：通过关卡生成的草稿，逐人编辑后发送 -->
        <el-tab-pane :label="`候选人通知${appNoticesList.length ? `（${appNoticesList.length}）` : ''}`" name="notices" lazy>
          <p class="muted tab-hint">
            通过笔试 / 专业面 / HR 面 / 终面时按模板生成草稿（模板在「系统设置」里改）；
            草稿候选人不可见，编辑确认「发送」后，候选人登录即弹窗。
          </p>
          <div v-if="appNoticesList.length" class="notice-admin-list">
            <div v-for="n in appNoticesList" :key="n.id" class="notice-admin-item">
              <div class="notice-admin-head">
                <el-tag size="small" effect="plain">{{ STAGE_LABELS_LOCAL[n.stage] || n.stage }}</el-tag>
                <template v-if="n.send_time">
                  <el-tag size="small" type="success" effect="plain">已发送</el-tag>
                  <span class="muted ats-nums">{{ fmtTime(n.send_time) }}</span>
                </template>
                <template v-else>
                  <el-tag size="small" type="warning" effect="plain">待发送</el-tag>
                  <span v-if="n.read_time" class="muted">候选人已读</span>
                </template>
              </div>

              <template v-if="noticeEdit?.id === n.id">
                <el-input v-model="noticeEdit.title" maxlength="100" placeholder="通知标题" style="margin-top: 10px" />
                <RichTextEditor
                  v-model="noticeEdit.body"
                  placeholder="通知正文（占位符 {候选人} {岗位} {关卡} 已在生成时替换，可再修改）"
                  :min-height="90"
                  style="margin-top: 8px"
                />
                <div class="notice-admin-actions">
                  <el-button type="primary" size="small" :loading="noticeBusy" @click="saveNoticeEdit">保存</el-button>
                  <el-button size="small" @click="noticeEdit = null">取消</el-button>
                </div>
              </template>
              <template v-else>
                <div class="notice-admin-body">
                  <div class="notice-admin-title">{{ n.title }}</div>
                  <div v-if="n.body" class="notice-admin-text rich-body" v-html="n.body" />
                </div>
                <div v-if="!n.send_time" class="notice-admin-actions">
                  <el-button size="small" @click="startNoticeEdit(n)">编辑</el-button>
                  <el-button type="primary" size="small" @click="openSendPreview(n)">发送</el-button>
                  <el-button size="small" type="danger" plain @click="discardNotice(n)">不发送</el-button>
                </div>
              </template>
            </div>
          </div>
          <el-empty v-else description="还没有通知；通过上述四关后会按模板生成草稿" :image-size="72" />
        </el-tab-pane>

        <el-tab-pane label="各关记录" name="notes" lazy>
          <!-- 各关负责人总览：7 关归谁管一眼看全（含技术端预指派、还没走到的关） -->
          <div class="stage-owner-strip" aria-label="各关负责人总览">
            <div
              v-for="st in (app.stages || [])"
              :key="st.stage"
              class="owner-chip"
              :class="{ current: st.is_current }"
            >
              <i class="chip-dot" :style="{ background: STAGE_COLOR[st.stage] }" />
              <span class="chip-stage">{{ st.label }}</span>
              <span class="chip-owner" :class="{ claimed: !!stageOwnerName(st.stage) }">
                {{ stageOwnerName(st.stage) || '未认领' }}
              </span>
            </div>
          </div>
          <p class="muted tab-hint">补写各关的通过 / 淘汰原因与面试评价</p>
          <template v-if="noteStages.length">
            <!-- 滑动选关：滑块停在哪个关，下面就展示哪个关的记录 -->
            <el-slider
              v-model="noteIndex"
              :min="0"
              :max="noteStages.length - 1"
              :step="1"
              :show-tooltip="false"
              :marks="noteMarks"
              class="note-slider"
            />

            <!-- 就地编辑表单：排版对齐面试登记表（分组头 + 两列栅格，文本域跨双列） -->
            <template v-if="selectedNote">
              <div class="note-section">
                <i class="note-section-bar" :style="{ background: STAGE_COLOR[selectedNote.stage] }" />
                <div class="note-section-main">
                  <h4 class="note-section-title">{{ selectedNote.label }}</h4>
                  <span v-if="selectedNote.time" class="muted ats-nums">{{ fmtTime(selectedNote.time) }}</span>
                </div>
                <el-tag v-if="selectedNote.result" size="small" effect="light" :type="selectedNote.result === 'pass' ? 'success' : 'danger'">
                  {{ RESULT_LABEL[selectedNote.result] }}
                </el-tag>
                <el-tag
                  size="small"
                  :type="selectedStageEditable ? 'success' : 'info'"
                  :effect="selectedStageEditable ? 'light' : 'plain'"
                  :title="selectedStageEditable ? '你是本关负责人（或关卡未认领）' : '本阶段由其他 HR 负责，你只能查看'"
                >
                  负责人：{{ stageOwnerName(selectedNote.stage) || '未认领' }}
                </el-tag>
              </div>

              <div class="note-panel">
                <el-form class="note-form" label-position="top" @submit.prevent>
                <el-form-item label="结果">
                  <el-select
                    v-model="noteResult"
                    :disabled="!noteResultEditable || !selectedStageEditable"
                    style="width: 100%"
                    @change="onNoteResultChange"
                  >
                    <el-option label="进行中（未定）" value="" />
                    <el-option label="通过" value="pass" />
                    <el-option label="淘汰" value="fail" />
                  </el-select>
                </el-form-item>

                <div class="span-2 muted result-hint">
                  {{
                    noteResultEditable
                      ? '改结果即执行推进 / 淘汰；历史关的结果请用顶部「撤回」'
                      : '历史关的结果已锁定，原因与评价随时可补写'
                  }}
                </div>

                <el-form-item class="span-2" label="淘汰或者通过原因">
                  <el-input
                    v-model="noteForm.reason"
                    type="textarea"
                    :autosize="{ minRows: 3 }"
                    maxlength="2000"
                    show-word-limit
                    :placeholder="noteReasonPlaceholder"
                  />
                </el-form-item>

                <el-form-item v-if="noteHasEvaluation" class="span-2">
                  <template #label>
                    <span class="eval-label">
                      面试评价
                      <el-button link type="primary" size="small" @click="aiOpen = !aiOpen">
                        {{ aiOpen ? '收起 AI 生成' : 'AI 生成' }}
                      </el-button>
                    </span>
                  </template>

                <el-collapse-transition>
                  <div v-if="aiOpen" class="ai-box">
                    <div class="muted ai-tip">
                      把这一轮的面试逐字稿整段贴进来，点「生成」按固定模板写一版评价，填进下面的评价框后可再修改。
                    </div>
                    <el-input
                      v-model="transcript"
                      type="textarea"
                      aria-label="面试逐字稿"
                      :rows="5"
                      placeholder="面试官 10:30:13&#10;你现在厦门吗？&#10;候选人 10:30:24&#10;对，在厦门。"
                    />
                    <div class="ai-actions">
                      <span class="muted" :class="{ over: transcriptLen > 30000 }">{{ transcriptLen }} 字（上限 3 万）</span>
                      <span class="ai-actions-right">
                        <span v-if="configUsed" class="muted">由「{{ configUsed }}」生成</span>
                        <el-button size="small" type="primary" :loading="aiRunning" :disabled="!canGenerate" @click="generateEvaluation">
                          {{ aiRunning ? 'AI 生成中…' : '生成并填入' }}
                        </el-button>
                      </span>
                    </div>
                  </div>
                </el-collapse-transition>

                <el-input
                  v-model="noteForm.evaluation"
                  type="textarea"
                  :autosize="{ minRows: 6 }"
                  maxlength="10000"
                  show-word-limit
                  placeholder="面试评价：可手写，也可用上面的「AI 生成」起草后修改。"
                />
              </el-form-item>

                <div class="span-2 note-save">
                  <el-button type="primary" :loading="noteSaving" :disabled="!selectedStageEditable" @click="saveNoteInline">
                    {{ selectedStageEditable ? '保存本关记录' : '本阶段由其他 HR 负责，只读' }}
                  </el-button>
                </div>
              </el-form>
              </div>
            </template>
          </template>
          <p v-else class="muted note-empty">还没有可记录的阶段（AI 筛选的理由见上方）。推进到人工环节后，可在这里写原因与面试评价。</p>
        </el-tab-pane>
      </el-tabs>
    </template>

    <!-- Offer 文件预览：PDF / 图片在线检查后再发送 -->
    <el-dialog
      :model-value="preview.visible"
      :title="`预览：${preview.name}`"
      class="ats-dialog-full"
      destroy-on-close
      @close="previewClose"
    >
      <div class="preview-offer-body">
        <iframe
          v-if="preview.type === 'pdf'"
          :src="preview.url"
          class="preview-frame"
          :title="preview.name"
        />
        <img v-else-if="preview.type === 'image'" :src="preview.url" class="preview-img" :alt="preview.name" />
        <div v-else class="preview-fallback">
          <p>该文件格式（如 Word）不支持在线预览</p>
          <el-button type="primary" @click="preview.visible = false">知道了，直接下载检查</el-button>
        </div>
      </div>
    </el-dialog>
    <!-- 发送前预览：所见即候选人弹窗所得，可直接在预览里编辑 -->
    <el-dialog
      :model-value="!!sendPreview"
      title="发送前预览（候选人看到的样式）"
      width="1080px"
      class="send-preview-dialog"
      modal-class="send-preview-overlay"
      append-to-body
      destroy-on-close
      @close="sendPreview = null"
    >
      <template v-if="sendPreview">
        <div class="send-preview-edit">
          <el-input v-model="sendPreview.title" maxlength="100" placeholder="通知标题" />
          <RichTextEditor
            v-model="sendPreview.body"
            placeholder="通知正文：可用加粗、字号、链接等排版"
            :min-height="90"
            style="margin-top: 8px"
          />
        </div>

        <div class="send-preview-hint muted">下面是候选人登录时弹窗的样子（实时预览）：</div>
        <div class="candidate-notice-mock">
          <div class="mock-item mock-unread">
            <div class="mock-head">
              <span class="mock-title">{{ sendPreview.title || '（标题）' }}</span>
              <el-tag size="small" type="danger" effect="light">新</el-tag>
            </div>
            <div v-if="sendPreview.body" class="mock-body rich-body" v-html="sendPreview.body" />
            <div class="muted mock-time">{{ sendPreviewTime }}</div>
          </div>
        </div>
      </template>
      <template #footer>
        <el-button @click="sendPreview = null">取消</el-button>
        <el-button type="primary" :loading="noticeBusy" @click="confirmSendPreview">确认发送</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
}

/* ---- 信息带 ---- */
.meta-band {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ats-sp-6);
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-3) var(--ats-sp-4);
  margin-bottom: var(--ats-sp-4);
}
.meta-item {
  display: flex;
  align-items: baseline;
  gap: var(--ats-sp-2);
}
.meta-label {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.meta-value {
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-primary);
  overflow-wrap: anywhere;
}

/* ---- 分区面板 ---- */
.panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-4);
  margin-bottom: var(--ats-sp-4);
}
.panel h3 {
  margin: 0 0 var(--ats-sp-3);
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
}
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ats-sp-3);
}

/* ---- AI 筛选：并进流程面板，一行信息带 ---- */
.ai-band {
  display: flex;
  align-items: baseline;
  gap: var(--ats-sp-2);
  margin-top: var(--ats-sp-4);
  padding-top: var(--ats-sp-3);
  border-top: 1px dashed var(--el-border-color-lighter);
}
.ai-label {
  flex: none;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.ai-comment {
  margin: 0;
  line-height: 1.8;
  color: var(--el-text-color-regular);
  overflow-wrap: anywhere;
}

/* ---- 详情标签页（附件材料 / 各份答卷 / 各关记录）---- */
.detail-tabs {
  margin-bottom: var(--ats-sp-4);
}
.detail-tabs .el-tabs__header {
  margin-bottom: var(--ats-sp-3);
}
.tab-hint {
  margin: 0 0 var(--ats-sp-3);
}
.submission-answers {
  padding: var(--ats-sp-3) var(--ats-sp-4);
  background: var(--el-fill-color-lighter);
  border-radius: var(--ats-radius);
}

/* ---- 管线 ---- */
.pipeline {
  list-style: none;
  margin: var(--ats-sp-6) 0 var(--ats-sp-2);
  padding: 0;
  display: flex;
}
.node {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
  text-align: center;
}
/* 节点之间的连接线：左右各画半条，拼成一条贯穿的轨道 */
.node::before,
.node::after {
  content: '';
  position: absolute;
  top: 13px;
  height: 2px;
  background: var(--ats-track);
}
.node::before {
  left: 0;
  right: 50%;
}
.node::after {
  left: 50%;
  right: 0;
}
.node:first-child::before,
.node:last-child::after {
  display: none;
}
/* 走过的路：连接线染成阶段色，读起来是"进度在推进" */
.node.is-passed::before,
.node.is-passed::after,
.node.is-rejected::before,
.node.is-current::before {
  background: var(--ats-stage-5);
}

.node-dot {
  position: relative;
  z-index: 1;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
}
/* 未到达：空心描边，形状保留但退到背景里 */
.node.is-upcoming .node-dot {
  background: var(--el-bg-color) !important;
  border: 2px solid var(--ats-track);
}
/* 当前：加一圈光晕，明确"停在这一关" */
.node.is-current .node-dot {
  box-shadow: 0 0 0 4px var(--el-color-primary-light-8);
}
/* 淘汰：整节点用语义色，读起来是"终止" */
.node.is-rejected .node-dot {
  background: var(--el-color-danger) !important;
  box-shadow: 0 0 0 4px var(--el-color-danger-light-9);
}

.node-name {
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-regular);
  font-weight: var(--ats-fw-medium);
}
.node.is-upcoming .node-name {
  color: var(--el-text-color-placeholder);
  font-weight: var(--ats-fw-normal);
}
.node-result {
  font-size: var(--ats-fs-label);
}
.node-result.pass {
  color: var(--el-color-success);
}
.node-result.fail {
  color: var(--el-color-danger);
}
.node-result.current {
  color: var(--el-color-primary);
}
.node-time {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
}

/* 个人信息 / 附件材料：表格四角圆角化 */
.profile-desc,
.rounded-table {
  border-radius: var(--ats-radius);
  overflow: hidden;
}
/* 个人信息页签：网格表格，标签列固定宽，简历行文件名与下载并排 */
.profile-desc :deep(.el-descriptions__label) {
  width: 110px;
}
.resume-name {
  margin-right: var(--ats-sp-3);
  overflow-wrap: anywhere;
}
.profile-actions {
  margin-top: var(--ats-sp-3);
}
.profile-desc :deep(.el-select) {
  width: 100%;
}
.send-time {
  margin-left: 6px;
}
.offer-upload-btns {
  display: flex;
  gap: var(--ats-sp-2);
}
.preview-offer-body {
  min-height: 200px;
}
.preview-frame {
  width: 100%;
  height: 68vh;
  border: 0;
  border-radius: var(--ats-radius);
}
.preview-img {
  display: block;
  max-width: 100%;
  margin: 0 auto;
}
.preview-fallback {
  text-align: center;
  padding: var(--ats-sp-6) 0;
}
.profile-desc :deep(.el-input),
.profile-desc :deep(.el-textarea) {
  width: 100%;
}
.ai-comment {
  margin: var(--ats-sp-2) 0 0;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

/* ---- 各关记录：滑动选关 ---- */
.note-slider {
  /* 居中、缩短轨道：两端刻度文字有地方放，不再被裁掉 */
  max-width: 72%;
  margin: var(--ats-sp-3) auto var(--ats-sp-6);
}
/* 加粗：轨道加厚、滑块加大、刻度文字加重 */
.note-slider :deep(.el-slider__runway) {
  height: 10px;
  border-radius: 5px;
}
.note-slider :deep(.el-slider__bar) {
  height: 10px;
  border-radius: 5px;
}
.note-slider :deep(.el-slider__button-wrapper) {
  top: -15px;
}
.note-slider :deep(.el-slider__button) {
  width: 24px;
  height: 24px;
  border: 3px solid var(--el-color-primary);
  box-shadow: 0 2px 8px rgb(10 40 36 / 18%);
}
.note-slider :deep(.el-slider__stop) {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}
.note-slider :deep(.el-slider__marks-text) {
  font-size: var(--ats-fs-body);
  font-weight: var(--ats-fw-medium);
  transform: translateX(-50%) !important;
}
/* 与管线里同一关同色的小色条，让两处一眼对得上 */
.note-dot {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  flex: none;
}
/* 分组头：对齐面试登记表的 section 样式（浅底 + 阶段色条 + 关卡名） */
.note-section {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
  margin: 0 0 var(--ats-sp-3);
  padding: 9px 14px;
  border-radius: 4px;
  background: var(--el-fill-color-light);
}
.note-section-bar {
  width: 3px;
  height: 16px;
  border-radius: 2px;
  flex: none;
}
.note-section-main {
  display: flex;
  align-items: baseline;
  gap: var(--ats-sp-2);
  flex: 1;
  min-width: 0;
}
.note-section-title {
  margin: 0;
  font-size: 14px;
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}

/* 表单栅格：与面试登记表渲染器同款两列布局，文本域跨双列 */
.note-form :deep(.el-form) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 24px;
  row-gap: 20px;
}
.note-form :deep(.el-form-item__label) {
  padding-bottom: 6px;
}
.note-form .span-2 {
  grid-column: 1 / -1;
}
.note-form :deep(.el-form-item) {
  margin-bottom: 0;
  min-width: 0;
}
.note-form :deep(.el-form-item__label) {
  padding-bottom: 4px;
  line-height: 1.4;
}
.result-hint {
  margin-top: 2px;
  font-size: var(--ats-fs-label);
  line-height: 1.7;
}
/* 表单底下垫一层表格式面板底：白底 + 细边框 + 圆角，和页面其他表格一个语言 */
.note-panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-4);
}
.note-save {
  margin-top: var(--ats-sp-2);
}
.eval-label {
  display: inline-flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
.ai-box {
  width: 100%;
  margin-bottom: var(--ats-sp-3);
  padding: var(--ats-sp-3);
  border-radius: var(--ats-radius);
  background: var(--el-fill-color-lighter);
}
.ai-tip {
  margin-bottom: var(--ats-sp-2);
  line-height: 1.7;
}
.ai-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--ats-sp-2);
}
.ai-actions-right {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
.over {
  color: var(--el-color-danger);
}
.note-empty {
  margin: var(--ats-sp-3) 0 0;
}

/* ---- 候选人通知管理 ---- */
.notice-admin-list {
  display: flex;
  flex-direction: column;
  gap: var(--ats-sp-3);
}
.notice-admin-item {
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-3);
}
.notice-admin-head {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
.notice-admin-body {
  margin-top: var(--ats-sp-2);
}
.notice-admin-title {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
.notice-admin-text {
  margin: var(--ats-sp-1) 0 0;
  font-size: var(--ats-fs-body);
  line-height: 1.8;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.notice-admin-actions {
  display: flex;
  gap: var(--ats-sp-2);
  margin-top: var(--ats-sp-3);
}

.stage-owner-tag {
  margin-right: var(--ats-sp-2);
  color: var(--el-text-color-regular);
}

/* ---- 各关负责人总览条：色点=关卡，灰=未认领 ---- */
.stage-owner-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 10px;
  margin-bottom: var(--ats-sp-3);
}
.owner-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--el-fill-color-lighter);
  font-size: 12px;
}
.owner-chip.current {
  background: var(--el-color-primary-light-9);
}
.chip-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex: none;
}
.chip-stage {
  color: var(--el-text-color-secondary);
}
.chip-owner {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-placeholder);
}
.chip-owner.claimed {
  color: var(--el-text-color-primary);
}

/* ---- 发送前预览（候选人弹窗样式）---- */
.send-preview-hint {
  margin: var(--ats-sp-3) 0 var(--ats-sp-2);
  font-size: var(--ats-fs-label);
}
.candidate-notice-mock {
  padding: var(--ats-sp-3);
  border: 1px dashed var(--el-border-color);
  border-radius: var(--ats-radius);
  background: var(--el-bg-color-page);
}
.mock-item {
  padding: var(--ats-sp-3);
  border-radius: var(--ats-radius);
  background: var(--el-fill-color-lighter);
}
.mock-unread {
  background: var(--el-color-primary-light-9);
}
.mock-head {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
.mock-title {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
.mock-body {
  margin: var(--ats-sp-2) 0 0;
  font-size: var(--ats-fs-body);
  line-height: 1.8;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.mock-time {
  margin-top: var(--ats-sp-2);
  font-size: var(--ats-fs-label);
}

/* 发送前预览弹窗：毛玻璃本体 + 大圆角（class 挂在 .el-dialog 自身，用复合选择器） */
:global(.el-overlay.send-preview-overlay) {
  background: rgb(0 0 0 / 12%) !important;
}
:global(.el-dialog.send-preview-dialog) {
  width: min(1080px, calc(100vw - 64px));
  background: color-mix(in srgb, var(--el-bg-color) 32%, transparent);
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid color-mix(in srgb, var(--el-bg-color) 45%, transparent);
  border-radius: 32px;
  box-shadow: 0 24px 80px rgb(10 40 36 / 18%);
  overflow: hidden;
}
.mock-body :deep(.offer-file-list ul) {
  margin: 6px 0 0;
  padding-left: 18px;
}

/* 富文本正文：渲染层统一排版（字号/链接跟随编辑效果） */
.rich-body {
  font-size: var(--ats-fs-body);
  line-height: 1.8;
  color: var(--el-text-color-regular);
  overflow-wrap: anywhere;
}
.rich-body :deep(a) {
  color: var(--el-color-primary);
  text-decoration: underline;
}
.rich-body :deep(font[size="2"]) {
  font-size: var(--ats-fs-label);
}
.rich-body :deep(font[size="5"]) {
  font-size: var(--ats-fs-card);
}
</style>
