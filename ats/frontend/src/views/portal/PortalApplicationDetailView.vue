<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { portalApplicationApi, portalFileApi, portalNoticeApi } from '../../api/portal'
import { STATUS_LABEL } from '../../constants'
import { fmtTime } from '../../utils/format'

const route = useRoute()

const app = ref(null)
const loading = ref(true)
const downloading = ref(false)
const notices = ref([])
const noticeIndex = ref('0')
// 页签文字 = 通过的关卡（笔试 / 专业面 / HR面 / 终面 / 入职）
const NOTICE_STAGE_LABEL = { phone: '电话沟通', test: '笔试', pro: '专业面', hr: 'HR面', final: '终面', onboard: '入职' }
const stageLabelOf = (n) => NOTICE_STAGE_LABEL[n.stage] || n.stage
const selectedNotice = computed(() => notices.value[Number(noticeIndex.value)] || null)

async function load() {
  loading.value = true
  try {
    app.value = await portalApplicationApi.detail(route.params.id)
    // 这条投递收到的通知（含已读），按发送时间新的在前
    const list = await portalNoticeApi.list()
    notices.value = (list || [])
      .filter((n) => n.application_id === Number(route.params.id))
      .sort((a, b) => new Date(b.send_time) - new Date(a.send_time))
    noticeIndex.value = '0' 
  } finally {
    loading.value = false
  }
}

async function downloadResume() {
  if (!app.value?.resume) return
  downloading.value = true
  try {
    await portalFileApi.download({
      id: app.value.resume.file_id,
      original_name: app.value.resume.name,
    })
  } finally {
    downloading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="portal-page">
    <router-link :to="{ name: 'portal-applications' }" class="back-link">
      <el-icon><ArrowLeft /></el-icon> 返回我的投递
    </router-link>

    <template v-if="loading">
      <div class="portal-card"><el-skeleton :rows="6" animated /></div>
    </template>

    <template v-else-if="app">
      <section class="portal-card">
        <div class="detail-head">
          <div>
            <h1 class="detail-title">{{ app.position?.name || '岗位已删除' }}</h1>
            <div class="position-meta">
              <span>{{ fmtTime(app.update_time) }}</span>
              <span v-if="app.position_closed" class="closed">岗位已关闭</span>
            </div>
          </div>
          <span class="status-pill" :class="app.overall_status">
            {{ STATUS_LABEL[app.overall_status] || app.overall_status }}
          </span>
        </div>
      </section>

      <section class="portal-card">
        <h2 class="portal-section-title">招聘进度</h2>
        <ol class="portal-timeline">
          <li v-for="item in app.timeline" :key="item.stage" class="tl-item" :class="item.state">
            <span class="tl-dot" />
            <div>
              <div class="tl-title">
                {{ item.label }}
                <span v-if="item.state === 'current'" class="status-pill pending">当前</span>
                <span v-else-if="item.state === 'passed'" class="status-pill pass">已通过</span>
                <span v-else-if="item.state === 'failed'" class="status-pill fail">未通过</span>
              </div>
              <div v-if="item.time" class="tl-time">{{ fmtTime(item.time) }}</div>
            </div>
          </li>
        </ol>
      </section>

      <section v-if="notices.length" class="portal-card">
        <h2 class="portal-section-title">通知记录</h2>
        <!-- 页签选通知：一条通知一个页签，点选后下方展示 -->
        <el-tabs v-model="noticeIndex" class="notice-tabs">
          <el-tab-pane v-for="(n, i) in notices" :key="n.id" :label="stageLabelOf(n)" :name="String(i)" />
        </el-tabs>
        <div v-if="selectedNotice" class="notice-record">
          <div class="notice-record-head">
            <span class="notice-record-title">{{ selectedNotice.title }}</span>
            <el-tag v-if="!selectedNotice.read_time" size="small" type="danger" effect="light">未读</el-tag>
          </div>
          <div v-if="selectedNotice.body" class="notice-record-body rich-body" v-html="selectedNotice.body" />
          <div class="muted notice-record-time">{{ fmtTime(selectedNotice.send_time) }}</div>
        </div>
      </section>

      <section v-if="app.resume" class="portal-card">
        <h2 class="portal-section-title">简历</h2>
        <div class="file-row">
          <div class="file-icon"><el-icon><Document /></el-icon></div>
          <div class="file-main">
            <div class="file-name">{{ app.resume.name }}</div>
            <div class="file-meta">{{ Math.round((app.resume.size || 0) / 1024) }} KB · HR 上传</div>
          </div>
          <el-button size="small" :loading="downloading" @click="downloadResume">下载</el-button>
        </div>
      </section>

      <section v-if="app.position?.requirements" class="portal-card">
        <h2 class="portal-section-title">岗位要求</h2>
        <p class="jd-text">{{ app.position.requirements }}</p>
      </section>
    </template>

    <div v-else class="portal-empty">
      <el-icon><Tickets /></el-icon>
      <p>投递记录不存在</p>
      <el-button @click="router.replace({ name: 'portal-applications' })">回到我的投递</el-button>
    </div>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-secondary);
  text-decoration: none;
  font-size: var(--ats-fs-note);
  width: fit-content;
}
.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ats-sp-3);
}
.detail-title {
  margin: 0;
  font-size: 22px;
  font-weight: var(--ats-fw-bold);
}
.closed {
  color: var(--el-color-warning);
}
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ats-sp-3);
  padding: 12px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.form-row:last-child {
  border-bottom: 0;
}
.form-name {
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-primary);
}
.jd-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

/* ---- 通知记录 ---- */
.notice-tabs :deep(.el-tabs__item.is-active) {
  font-weight: var(--ats-fw-bold);
}
.notice-record {
  padding: var(--ats-sp-4);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--ats-radius);
  background: var(--el-fill-color-lighter);
}
.notice-record-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.notice-record-title {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
.notice-record-body {
  margin-top: 6px;
  font-size: var(--ats-fs-body);
  line-height: 1.8;
  color: var(--el-text-color-regular);
  overflow-wrap: anywhere;
}
.notice-record-body :deep(a) {
  color: var(--el-color-primary);
  text-decoration: underline;
}
.notice-record-time {
  margin-top: 6px;
  font-size: var(--ats-fs-label);
}
</style>
