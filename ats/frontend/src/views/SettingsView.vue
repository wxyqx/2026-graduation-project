<!--
  【HR 端系统设置】
  v3.15 起 AI 接口配置与 AI 筛选提示词已迁到技术管理端（/tech）。
  这里可配置：候选人在哪一关之后才能看到岗位申请表 / 职业底色图。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { settingsApi } from '../api'
import RichTextEditor from '../components/RichTextEditor.vue'
import { STAGES, STAGE_LABEL } from '../constants'

const stageOptions = STAGES.map((s) => ({ value: s.value, label: `从「${s.label}」起` }))
const saving = ref(false)
const cfg = reactive({ position: 'pro', assessment: 'pro' })

// ---- 通过/淘汰通知模板（各关通过 + 淘汰）----
// onboard（入职）/ eliminated（淘汰）不在 7 关 STAGE_LABEL 里，单独补名
const NOTICE_STAGE_LABELS = { ...STAGE_LABEL, onboard: '入职', eliminated: '淘汰' }
const NOTICE_STAGES = ['phone', 'test', 'pro', 'hr', 'final', 'onboard', 'eliminated']
const noticeSaving = ref(false)
// 占位符插入按钮：点一下在光标处插入，发送时后端自动替换
const NOTICE_PLACEHOLDERS = [
  { label: '候选人姓名', value: '{候选人}', hint: '自动替换为该候选人的姓名' },
  { label: '应聘岗位', value: '{岗位}', hint: '自动替换为投递的岗位名' },
  { label: '所在关卡', value: '{关卡}', hint: '自动替换为通过/被淘汰的关卡名' },
  { label: '环节负责人', value: '{负责人}', hint: '通过=下一关负责人（接下来由谁负责），淘汰=本关负责人（评估人）；未指派时为候选人负责人' },
]

// 声明时就初始化四关，避免接口返回前模板读到 undefined 报错
const noticeCfg = reactive(
  Object.fromEntries(NOTICE_STAGES.map((st) => [st, { enabled: true, title: '', body: '' }])),
)
// 六个模板用页签（el-tabs）折叠，一次只展开一关
const noticeTab = ref('phone')

// ---- 发送效果预览：占位符用示例值渲染成候选人弹窗的样子 ----
const previewVisible = ref(false)
const previewStage = ref('phone')
const previewTime = computed(() => new Date().toLocaleString())
const previewTitle = computed(() => renderSample(noticeCfg[previewStage.value].title, previewStage.value))
const previewBody = computed(() => renderSample(noticeCfg[previewStage.value].body, previewStage.value))

// 占位符替换成示例值（{关卡}：淘汰模板预览时用「专业面」当示例，其余用本关名）
function renderSample(text, st) {
  const values = {
    候选人: '张三',
    岗位: '示例岗位',
    关卡: st === 'eliminated' ? '专业面' : stageLabel[st],
    负责人: st === 'eliminated' ? '李评估' : '王面试官',
  }
  for (const [k, v] of Object.entries(values)) text = (text || '').replaceAll(`{${k}}`, v)
  return text
}

function openPreview(st) {
  previewStage.value = st
  previewVisible.value = true
}

async function loadNotice() {
  const data = await settingsApi.getStageNotice()
  for (const st of NOTICE_STAGES) {
    noticeCfg[st] = {
      enabled: data[st]?.enabled ?? true,
      title: data[st]?.title || '',
      body: data[st]?.body || '',
    }
  }
}

async function saveNotice() {
  noticeSaving.value = true
  try {
    const payload = {}
    for (const st of NOTICE_STAGES) payload[st] = { ...noticeCfg[st] }
    const data = await settingsApi.saveStageNotice(payload)
    for (const st of NOTICE_STAGES) {
      noticeCfg[st] = { enabled: data[st]?.enabled ?? true, title: data[st]?.title || '', body: data[st]?.body || '' }
    }
    ElMessage.success('通知模板已保存')
  } finally {
    noticeSaving.value = false
  }
}

const stageLabel = NOTICE_STAGE_LABELS

async function load() {
  const data = await settingsApi.getPortalFormStage()
  cfg.position = data.position
  cfg.assessment = data.assessment
}

async function save() {
  saving.value = true
  try {
    const data = await settingsApi.savePortalFormStage({ ...cfg })
    cfg.position = data.position
    cfg.assessment = data.assessment
    ElMessage.success('已保存，候选人端即时生效')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  load()
  loadNotice()
})
</script>

<template>
  <div>
    <div class="page-header">
      <h2>系统设置</h2>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="AI 配置与筛选提示词已迁移到技术管理端"
      description="HR 端不再提供 AI 配置入口。需要更换模型、密钥或调整筛选规则时，请联系公司技术人员。"
      class="tip"
    />

    <section class="ats-panel">
      <h3 class="title">候选人表单可见阶段</h3>
      <p class="muted">
        控制候选人在招聘流程走到哪一关后，才能看到并填写岗位申请表、职业底色图。
        个人资料表不受影响，投递前始终要填；被淘汰的候选人停在某一关，按所在关判断。
        保存后候选人端即时生效。
      </p>
      <div class="stage-row">
        <span class="stage-label">岗位申请表</span>
        <el-select v-model="cfg.position" style="width: 200px">
          <el-option v-for="o in stageOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </div>
      <div class="stage-row">
        <span class="stage-label">职业底色图</span>
        <el-select v-model="cfg.assessment" style="width: 200px">
          <el-option v-for="o in stageOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
      </div>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </section>

    <section class="ats-panel" style="margin-top: 16px">
      <h3 class="title">通过 / 淘汰通知模板</h3>
      <p class="muted">
        候选人通过笔试 / 专业面 / HR 面 / 终面时，按这里的模板给他发一条通知，候选人下次登录会弹窗展示；
        被淘汰时按「淘汰」模板立即发送（候选人两天保留期内登录可见，超期登录通道关闭，拦截信息也用此模板）；
        关掉开关则不发。正文里点「候选人姓名 / 应聘岗位 / 所在关卡」按钮即可插入占位符，
        发送时自动替换成每位候选人的真实信息（<code>{候选人}</code> <code>{岗位}</code> <code>{关卡}</code> <code>{负责人}</code>——通过=下一关负责人、淘汰=本关负责人）。
      </p>
      <el-tabs v-model="noticeTab" class="notice-tabs">
        <el-tab-pane v-for="st in NOTICE_STAGES" :key="st" :name="st">
          <template #label>
            <span class="notice-tab-label">
              {{ stageLabel[st] }}
              <el-tag v-if="!noticeCfg[st].enabled" size="small" type="info" effect="plain">停用</el-tag>
            </span>
          </template>
          <div class="notice-head-row">
            <span class="notice-stage-name">{{ stageLabel[st] }}通知模板</span>
            <div class="notice-head-actions">
              <el-button size="small" @click="openPreview(st)">预览发送效果</el-button>
              <el-switch
                v-model="noticeCfg[st].enabled"
                :active-text="st === 'eliminated' ? '淘汰时发送' : '通过时发送'"
              />
            </div>
          </div>
          <el-input v-model="noticeCfg[st].title" maxlength="100" placeholder="通知标题" style="margin-top: 8px" />
          <RichTextEditor
            v-model="noticeCfg[st].body"
            placeholder="通知正文：支持加粗、字号、对齐、链接等排版；点上方按钮插入占位符，发送时自动替换"
            :min-height="110"
            :placeholders="NOTICE_PLACEHOLDERS"
            style="margin-top: 8px"
          />
        </el-tab-pane>
      </el-tabs>
      <el-button type="primary" :loading="noticeSaving" @click="saveNotice">保存通知模板</el-button>
    </section>

    <section class="ats-panel" style="margin-top: 16px">
      <h3 class="title">技术管理端</h3>
      <p class="muted">
        技术管理端负责：账号与权限、AI 接口配置与提示词、操作日志、数据备份与运行概览。
        技术管理员使用独立入口登录，不占用 HR 账号，也不能浏览招聘业务数据。
      </p>
      <router-link to="/tech/login" class="tech-link">打开技术管理端登录页</router-link>
    </section>

    <section class="ats-panel" style="margin-top: 16px">
      <h3 class="title">主题与界面</h3>
      <p class="muted">
        三档主题（白天青碧 / 黑夜 / 护眼墨绿）在顶栏右侧切换，选择保存在本浏览器。
        周报阶段文案的改写仍在「汇总导出」页内，不需要来本页。
      </p>
    </section>

    <!-- 通知模板发送效果预览：所见即候选人登录弹窗所得（占位符用示例值渲染） -->
    <el-dialog
      v-model="previewVisible"
      :title="`发送效果预览（${stageLabel[previewStage]} · 候选人登录弹窗样式）`"
      width="680px"
      append-to-body
      destroy-on-close
    >
      <p class="muted" style="margin-top: 0">
        占位符已用示例值渲染：{候选人}=张三，{岗位}=示例岗位，{关卡}={{ previewStage === 'eliminated' ? '专业面' : stageLabel[previewStage] }}，{负责人}={{ previewStage === 'eliminated' ? '李评估（本关负责人）' : '王面试官（下一关负责人）' }}。
      </p>
      <div class="candidate-notice-mock">
        <div class="mock-item mock-unread">
          <div class="mock-head">
            <span class="mock-title">{{ previewTitle || '（标题）' }}</span>
            <el-tag size="small" type="danger" effect="light">新</el-tag>
          </div>
          <div v-if="previewBody" class="mock-body rich-body" v-html="previewBody" />
          <div class="muted mock-time">{{ previewTime }}</div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="previewVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tip {
  margin-bottom: var(--ats-sp-4);
}
.title {
  margin: 0 0 var(--ats-sp-2);
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
}
p.muted {
  margin-top: 0;
  line-height: 1.7;
}
.stage-row {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
  margin-bottom: var(--ats-sp-3);
}
.stage-label {
  width: 90px;
  color: var(--el-text-color-regular);
}
.tech-link {
  display: inline-flex;
  align-items: center;
  padding: 7px 14px;
  border: 1px solid var(--el-color-primary-light-5);
  border-radius: var(--ats-radius-sm);
  color: var(--el-color-primary);
  text-decoration: none;
  font-size: var(--ats-fs-note);
}
.tech-link:hover {
  background: var(--el-color-primary-light-9);
}

/* 通知模板页签：与投递详情的页签风格一致（激活即主题色下划线） */
.notice-tabs :deep(.el-tabs__item) {
  font-size: var(--ats-fs-body);
}
.notice-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}
.notice-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 2px;
}
.notice-head-actions {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
}
.notice-stage-name {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}

/* ---- 发送效果预览（候选人弹窗样式，与投递详情页发送预览一致）---- */
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
