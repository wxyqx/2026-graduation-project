<!--
  【HR 端系统设置】
  v3.15 起 AI 接口配置与 AI 筛选提示词已迁到技术管理端（/tech）。
  这里可配置：候选人在哪一关之后才能看到岗位申请表 / 职业底色图。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { settingsApi } from '../api'
import RichTextEditor from '../components/RichTextEditor.vue'
import { STAGES, STAGE_LABEL } from '../constants'

const stageOptions = STAGES.map((s) => ({ value: s.value, label: `从「${s.label}」起` }))
const saving = ref(false)
const cfg = reactive({ position: 'pro', assessment: 'pro' })

// ---- 通过通知模板（笔试/专业面/HR面/终面）----
// onboard（入职）不在 7 关 STAGE_LABEL 里，单独补名
const NOTICE_STAGE_LABELS = { ...STAGE_LABEL, onboard: '入职' }
const NOTICE_STAGES = ['phone', 'test', 'pro', 'hr', 'final', 'onboard']
const noticeSaving = ref(false)
// 声明时就初始化四关，避免接口返回前模板读到 undefined 报错
const noticeCfg = reactive(
  Object.fromEntries(NOTICE_STAGES.map((st) => [st, { enabled: true, title: '', body: '' }])),
)

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
      <h3 class="title">通过通知模板</h3>
      <p class="muted">
        候选人通过笔试 / 专业面 / HR 面 / 终面时，按这里的模板给他发一条通知，候选人下次登录会弹窗展示；
        关掉开关则不发。占位符：<code>{候选人}</code> <code>{岗位}</code> <code>{关卡}</code>，发送时自动替换。
      </p>
      <div v-for="st in NOTICE_STAGES" :key="st" class="notice-block">
        <div class="notice-head-row">
          <span class="notice-stage-name">{{ stageLabel[st] }}</span>
          <el-switch v-model="noticeCfg[st].enabled" active-text="通过时发送" />
        </div>
        <el-input v-model="noticeCfg[st].title" maxlength="100" placeholder="通知标题" style="margin-top: 8px" />
        <RichTextEditor
          v-model="noticeCfg[st].body"
          placeholder="通知正文：支持加粗、字号、对齐、链接等排版；占位符 {候选人} {岗位} {关卡} 发送时替换"
          :min-height="110"
          style="margin-top: 8px"
        />
      </div>
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

.notice-block {
  padding: var(--ats-sp-3);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--ats-radius);
  margin-bottom: var(--ats-sp-3);
}
.notice-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.notice-stage-name {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
</style>
