<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import PortalStageBar from '../../components/PortalStageBar.vue'
import { portalApplicationApi } from '../../api/portal'
import { STATUS_LABEL } from '../../constants'
import { fmtTime } from '../../utils/format'

const router = useRouter()
const applications = ref([])
const loading = ref(true)

function aiText(app) {
  if (app.ai_result === 'pass') return 'AI 初筛通过'
  if (app.ai_result === 'fail') return 'AI 初筛未通过'
  return '待 HR 筛选'
}

async function load() {
  loading.value = true
  try {
    applications.value = await portalApplicationApi.list()
  } finally {
    loading.value = false
  }
}

function open(app) {
  router.push({ name: 'portal-application-detail', params: { id: app.id } })
}

onMounted(load)
</script>

<template>
  <div class="portal-page apps-page">
    <header class="apps-head">
      <div class="apps-title">
        <h1>我的投递</h1>
        <p class="portal-page-sub">投递后可以在详情里补填岗位申请表</p>
      </div>

      <el-button size="small" @click="router.push({ name: 'portal-positions' })">看岗位</el-button>
    </header>

    <template v-if="loading">
      <div v-for="i in 3" :key="i" class="portal-card"><el-skeleton :rows="3" animated /></div>
    </template>

    <div v-else-if="!applications.length" class="portal-empty">
      <el-icon><Tickets /></el-icon>
      <p>还没有投递记录</p>
      <el-button type="primary" @click="router.push({ name: 'portal-positions' })">去看看在招岗位</el-button>
    </div>

    <section v-else class="apps-board">
      <div class="apps-board-head" aria-hidden="true">
        <span>岗位</span>
        <span>招聘进度</span>
        <span>状态</span>
        <span>更新时间</span>
        <span />
      </div>

      <article
        v-for="app in applications"
        :key="app.id"
        class="app-row"
        tabindex="0"
        role="button"
        :aria-label="`查看投递 ${app.position?.name || ''}`"
        @click="open(app)"
        @keyup.enter="open(app)"
      >
        <div class="app-main">
          <h2 class="app-position">{{ app.position?.name || '岗位已删除' }}</h2>
          <div class="app-meta">
            <span>投递 #{{ app.id }}</span>
            <span>{{ aiText(app) }}</span>
            <span v-if="app.position_closed" class="closed">岗位已关闭</span>
          </div>
        </div>

        <div class="app-stage">
          <PortalStageBar :current-stage="app.current_stage" :status="app.overall_status" />
        </div>

        <div class="app-status">
          <span class="status-pill" :class="app.overall_status">
            {{ STATUS_LABEL[app.overall_status] || app.overall_status }}
          </span>
        </div>

        <div class="app-time">{{ fmtTime(app.update_time) }}</div>

        <el-icon class="app-arrow"><ArrowRight /></el-icon>
      </article>
    </section>
  </div>
</template>

<style scoped>
.apps-page {
  gap: 20px;
}

/* ---- 页头 + 统计 ---- */
.apps-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--ats-sp-4);
  padding: 4px 2px 0;
}
.apps-title h1 {
  margin: 0;
  font-size: 24px;
  font-weight: var(--ats-fw-bold);
  letter-spacing: -0.01em;
}
.apps-title .portal-page-sub {
  margin: 4px 0 0;
}

/* ---- 桌面：占满宽度的行式列表 ---- */
.apps-board {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  overflow: hidden;
}
.apps-board-head,
.app-row {
  display: grid;
  grid-template-columns: minmax(200px, 1.15fr) minmax(300px, 1.7fr) 104px 148px 24px;
  align-items: center;
  gap: var(--ats-sp-4);
  padding: 0 var(--ats-sp-6);
}
.apps-board-head {
  height: 42px;
  background: var(--el-fill-color-light);
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.app-row {
  min-height: 84px;
  border-top: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  transition: background-color 0.15s;
}
.app-row:hover {
  background: var(--el-color-primary-light-9);
}
.app-row:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: -2px;
}
.app-position {
  margin: 0;
  font-size: 17px;
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.app-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 4px;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
}
.closed {
  color: var(--el-color-warning);
}
.app-stage {
  min-width: 0;
}
.app-status {
  justify-self: start;
}
.app-time {
  color: var(--el-text-color-secondary);
  font-size: var(--ats-fs-note);
  font-variant-numeric: var(--ats-nums);
  white-space: nowrap;
}
.app-arrow {
  color: var(--el-text-color-placeholder);
  transition: transform 0.15s, color 0.15s;
}
.app-row:hover .app-arrow {
  color: var(--el-color-primary);
  transform: translateX(3px);
}

/* ---- 手机：卡片 ---- */
@media (max-width: 759px) {
  .apps-head {
    align-items: flex-start;
    flex-direction: column;
    gap: var(--ats-sp-3);
  }
  .apps-board {
    background: transparent;
    border: 0;
    border-radius: 0;
    overflow: visible;
    display: flex;
    flex-direction: column;
    gap: var(--ats-sp-3);
  }
  .apps-board-head {
    display: none;
  }
  .app-row {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 10px 12px;
    padding: var(--ats-sp-4);
    background: var(--el-bg-color);
    border: 1px solid var(--el-border-color-light);
    border-radius: 12px;
    min-height: 0;
  }
  .app-main {
    grid-column: 1;
    grid-row: 1;
  }
  .app-status {
    grid-column: 2;
    grid-row: 1;
    align-self: start;
  }
  .app-stage {
    grid-column: 1 / -1;
    grid-row: 2;
    margin-top: 2px;
  }
  .app-time {
    grid-column: 1;
    grid-row: 3;
  }
  .app-arrow {
    display: none;
  }
}
</style>
