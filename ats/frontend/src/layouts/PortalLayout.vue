<!--
  【候选人端布局】移动优先
  顶部：品牌 + 当前候选人；桌面端显示横向导航
  底部：手机端固定 4 个入口（岗位 / 投递 / 文件 / 我的）
  内容区最大宽 720，桌面上居中显示，不做成后台那种左菜单。
-->
<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { portalApplicationApi, portalAuthApi, portalNoticeApi, portalPositionApi } from '../api/portal'
import { portalAuth } from '../stores/portalAuth'
import { THEMES, applyTheme, theme } from '../theme'
import UserAvatar from '../components/UserAvatar.vue'

const route = useRoute()
const router = useRouter()

const isWide = computed(() => route.meta.wide === true)
const themeIcon = computed(() => (theme.value === 'dark' ? 'Moon' : theme.value === 'eye' ? 'View' : 'Sunny'))
const me = computed(() => portalAuth.candidate.value || portalAuth.user.value || null)

const stats = ref({ positions: 0, total: 0, pending: 0, pass: 0 })

// ---- 通过关卡通知：只要在站内有未读就一直弹着，点「我知道了」才消失 ----
const notices = ref([])
const noticeVisible = ref(false)
// 记录已确认过的时间戳：确认后短时间内不因轮询再次弹出
let noticeTimer = 0
let acknowledging = false // 「我知道了」请求在途时不轮询，避免读到旧数据又弹出来

async function loadNotices() {
  if (acknowledging) return
  try {
    const list = await portalNoticeApi.list()
    notices.value = list || []
    // 只有存在未读才弹；确认后已全部已读，没发新通知就不会再弹
    noticeVisible.value = notices.value.some((n) => !n.read_time)
  } catch (e) {
    console.error('loadNotices failed:', e)
  }
}

async function acknowledgeNotices() {
  acknowledging = true
  try {
    const unread = notices.value.filter((n) => !n.read_time)
    for (const n of unread) {
      try {
        await portalNoticeApi.markRead(n.id)
      } catch {
        /* 单条失败忽略 */
      }
    }
    noticeVisible.value = false
    await loadNotices()
  } finally {
    acknowledging = false
  }
}

async function loadStats() {
  try {
    const [positions, applications] = await Promise.all([
      portalPositionApi.list(),
      portalApplicationApi.list(),
    ])
    stats.value = {
      positions: positions.length,
      total: applications.length,
      pending: applications.filter((a) => a.overall_status === 'pending').length,
      pass: applications.filter((a) => a.overall_status === 'pass').length,
    }
  } catch {
    /* 401 时拦截器处理；统计失败不影响页面 */
  }
}

const navItems = [
  { name: 'portal-positions', label: '岗位', icon: 'Briefcase', to: '/portal/positions' },
  { name: 'portal-applications', label: '投递', icon: 'Tickets', to: '/portal/applications' },
  { name: 'portal-files', label: '文件', icon: 'Document', to: '/portal/files' },
  { name: 'portal-profile', label: '我的', icon: 'User', to: '/portal/profile' },
]

function isActive(item) {
  if (item.to === '/portal/positions') {
    return route.path.startsWith('/portal/positions')
  }
  return route.path.startsWith(item.to)
}

async function refreshMe() {
  try {
    const data = await portalAuthApi.me()
    portalAuth.setProfile(data.user, data.candidate)
  } catch {
    /* 401 时拦截器会清状态并跳登录 */
  }
}

function onUserCommand(command) {
  if (command === 'profile') router.push({ name: 'portal-profile' })
  else if (command === 'logout') {
    portalAuth.clear()
    router.replace({ name: 'portal-login' })
  }
}

onMounted(() => {
  loadNotices()
  refreshMe()
  loadStats()
  noticeTimer = window.setInterval(loadNotices, 60_000)
})

onBeforeUnmount(() => {
  if (noticeTimer) window.clearInterval(noticeTimer)
})

watch(
  () => route.path,
  () => {
    loadStats()
    loadNotices()
  },
)
</script>

<template>
  <div class="portal-shell">
    <header class="portal-header">
      <router-link to="/portal/positions" class="portal-brand">
        <span class="brand-mark">ATS</span>
        <span class="brand-sub">招聘</span>
      </router-link>

      <nav class="portal-nav" aria-label="候选人端导航">
        <router-link
          v-for="item in navItems"
          :key="item.name"
          :to="item.to"
          class="portal-nav-link"
          :class="{ active: isActive(item) }"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <UserAvatar :fetch-blob="portalAuthApi.avatarBlob" :name="me?.name || me?.phone || '候选人'" :size="40" />

      <el-dropdown class="portal-theme-dropdown" trigger="click" @command="applyTheme">
        <button type="button" class="portal-theme" title="切换主题" aria-label="切换主题">
          <el-icon :size="17"><component :is="themeIcon" /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="t in THEMES"
              :key="t.value"
              :command="t.value"
              :class="{ 'is-current-theme': theme === t.value }"
            >
              {{ t.label }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>

      <el-dropdown trigger="click" @command="onUserCommand">
        <button class="portal-user" type="button">
          <el-icon><UserFilled /></el-icon>
          <span class="portal-user-name">{{ portalAuth.displayName.value }}</span>
          <el-icon class="caret"><ArrowDown /></el-icon>
        </button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="profile">我的资料</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </header>

    <div class="portal-statusbar" aria-label="我的招聘概览">
      <div class="status-inner">
        <router-link :to="{ name: 'portal-positions' }" class="status-item">
          <span class="status-num">{{ stats.positions }}</span>
          <span class="status-label">在招岗位</span>
        </router-link>
        <router-link :to="{ name: 'portal-applications' }" class="status-item">
          <span class="status-num">{{ stats.total }}</span>
          <span class="status-label">我的投递</span>
        </router-link>
        <router-link :to="{ name: 'portal-applications' }" class="status-item is-pending">
          <span class="status-num">{{ stats.pending }}</span>
          <span class="status-label">进行中</span>
        </router-link>
        <router-link :to="{ name: 'portal-applications' }" class="status-item is-pass">
          <span class="status-num">{{ stats.pass }}</span>
          <span class="status-label">已录用</span>
        </router-link>
      </div>
    </div>

    <main class="portal-main" :class="{ 'portal-main--wide': isWide }">
      <router-view />
    </main>

    <nav class="portal-tabbar" aria-label="候选人端底部导航">
      <router-link
        v-for="item in navItems"
        :key="item.name"
        :to="item.to"
        class="tab-item"
        :class="{ active: isActive(item) }"
      >
        <el-icon :size="20"><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </router-link>
    </nav>

    <!-- 通过关卡通知：有未读就弹出（类似邮件） -->
    <el-dialog
      v-model="noticeVisible"
      title="通知"
      width="680px"
      class="notice-dialog"
      :close-on-click-modal="false"
      :close-on-escape="false"
      :show-close="false"
    >
      <div class="notice-list">
        <div v-for="n in notices" :key="n.id" class="notice-item" :class="{ unread: !n.read_time }">
          <div class="notice-head">
            <span class="notice-title">{{ n.title }}</span>
            <el-tag v-if="!n.read_time" size="small" type="danger" effect="light">新</el-tag>
          </div>
          <div v-if="n.body" class="notice-body rich-body" v-html="n.body" />
          <div class="muted notice-time">{{ new Date(n.send_time).toLocaleString() }}</div>
        </div>
      </div>
      <template #footer>
        <el-button type="primary" @click="acknowledgeNotices">我知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.portal-shell {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color-page);
}

.portal-header {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  align-items: center;
  gap: var(--ats-sp-4);
  height: 56px;
  padding: 0 var(--ats-sp-4);
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}

/* 参考 HR 顶栏的速览数字：候选人只看自己的四个数 */
.portal-statusbar {
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}
.status-inner {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  padding: 8px var(--ats-sp-4);
  box-sizing: border-box;
}
.status-item {
  display: flex;
  align-items: baseline;
  justify-content: center;
  gap: 7px;
  padding: 2px 0;
  border-left: 1px solid var(--el-border-color-lighter);
  text-decoration: none;
  color: var(--el-text-color-regular);
}
.status-item:first-child {
  border-left: 0;
}
.status-num {
  font-size: 17px;
  font-weight: var(--ats-fw-bold);
  line-height: 1.1;
  font-variant-numeric: var(--ats-nums);
  color: var(--el-text-color-primary);
}
.status-label {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.status-item:hover .status-num {
  color: var(--el-color-primary);
}
.status-item.is-pending .status-num {
  color: var(--el-color-primary);
}
.status-item.is-pass .status-num {
  color: var(--el-color-success);
}

.portal-brand {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  text-decoration: none;
  flex: none;
}
.brand-mark {
  font-size: 18px;
  font-weight: var(--ats-fw-bold);
  letter-spacing: 0.06em;
  color: var(--el-color-primary);
}
.brand-sub {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}

.portal-nav {
  display: none;
  gap: var(--ats-sp-4);
  margin-left: var(--ats-sp-4);
}
.portal-nav-link {
  position: relative;
  padding: 16px 2px;
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-regular);
  text-decoration: none;
}
.portal-nav-link.active {
  color: var(--el-color-primary);
  font-weight: var(--ats-fw-medium);
}
.portal-nav-link.active::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 2px;
  border-radius: 1px;
  background: var(--el-color-primary);
}

.portal-user {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--el-text-color-regular);
  font-size: var(--ats-fs-note);
  cursor: pointer;
  padding: 6px 4px;
}
.portal-theme-dropdown {
  margin-left: auto;
}
.portal-theme {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--el-text-color-secondary);
  cursor: pointer;
  flex: none;
}
.portal-theme:hover {
  background: var(--el-fill-color-light);
  color: var(--el-color-primary);
}
:deep(.is-current-theme) {
  color: var(--el-color-primary);
  font-weight: var(--ats-fw-medium);
}
.portal-user-name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.caret {
  color: var(--el-text-color-placeholder);
}

.portal-main {
  /* 桌面端占视口 75%，居中；移动端仍全宽 */
  width: 75%;
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--ats-sp-4);
  padding-bottom: calc(72px + env(safe-area-inset-bottom));
  flex: 1;
  box-sizing: border-box;
}
.portal-main--wide {
  max-width: 1400px;
}

.portal-tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  background: var(--el-bg-color);
  border-top: 1px solid var(--el-border-color-light);
  padding-bottom: env(safe-area-inset-bottom);
}
.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 8px 0 6px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  text-decoration: none;
}
.tab-item.active {
  color: var(--el-color-primary);
}

@media (max-width: 759px) {
  .status-inner {
    padding: 7px 8px;
  }
  .status-item {
    flex-direction: column;
    align-items: center;
    gap: 1px;
  }
  .status-num {
    font-size: 18px;
  }
  .status-label {
    font-size: 10px;
  }
}

@media (min-width: 760px) {
  .portal-nav {
    display: flex;
  }
  .portal-tabbar {
    display: none;
  }
  .portal-main {
    width: 100%;
    padding: var(--ats-sp-6);
  }
}

/* ---- 通过关卡通知弹窗：加宽、一条一条完整铺开，不在弹窗里滚动 ---- */
.notice-dialog .el-dialog__body {
  max-height: none;
  overflow: visible;
}
.notice-list {
  display: flex;
  flex-direction: column;
  gap: var(--ats-sp-4);
  max-height: none;
  overflow: visible;
}
.notice-item {
  padding: var(--ats-sp-3);
  border-radius: var(--ats-radius);
  background: var(--el-fill-color-lighter);
}
.notice-item.unread {
  background: var(--el-color-primary-light-9);
}
.notice-head {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
.notice-title {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
.notice-body {
  margin: var(--ats-sp-2) 0 0;
  font-size: var(--ats-fs-body);
  line-height: 1.8;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.notice-time {
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
