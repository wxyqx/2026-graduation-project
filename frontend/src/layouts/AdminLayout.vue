<!--
  【后台布局】登录后所有页面的「外框」：
    左边：可折叠菜单（岗位管理 / 候选人管理 / 投递列表 / 汇总导出 / 系统设置）
    顶部：4 个可读指标 + 三档主题切换 + 用户名/退出
    中间：router-view

  设计说明（v3.12）：
    · 顶栏原先挤了 5 个扁平数字，全是"数字 + 灰标签"的看板脸，扫不出重点。
      现在收敛成 4 个真正会看的指标，数字用等宽字体对齐，"待 AI 筛选"做成可点的待办入口。
    · 侧栏当前项用一条主色竖条标出，而不是整块高亮 —— 更安静，眼睛不用被大色块拽走。

  子页面改了数据后想让顶部数字刷新，调 inject('refreshStats')() 即可。
-->
<script setup>
import { computed, onMounted, provide, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { statsApi } from '../api'
import { auth } from '../stores/auth'
import { THEMES, applyTheme, theme } from '../theme'

const route = useRoute()
const router = useRouter()

const collapsed = ref(false)
// 详情页 /applications/7 也要让「投递列表」菜单亮着
const activeMenu = computed(() => (route.path.startsWith('/applications') ? '/applications' : route.path))

// ---- 顶栏指标 ----
const stats = ref(null)
async function refreshStats() {
  try {
    stats.value = await statsApi.overview()
  } catch {
    /* 拦截器已经弹了提示，这里不用再管 */
  }
}
provide('refreshStats', refreshStats)
onMounted(refreshStats)
watch(() => route.path, refreshStats) // 切页面时也刷新一次

// 只留 4 个会看的指标；"待 AI 筛选"是可点的待办
const quickStats = computed(() => {
  const s = stats.value
  return [
    { label: '在招岗位', value: s?.position_count, to: { name: 'positions' } },
    { label: '进行中', value: s?.pending_count, to: { name: 'applications', query: { status: 'pending' } } },
    { label: '待 AI 筛选', value: s?.ai_pending_count, to: { name: 'applications', query: { stage: 'ai' } }, todo: true },
    { label: '本周进行', value: s?.week_in_progress, to: { name: 'stats' } },
  ]
})

function logout() {
  auth.clear()
  router.replace({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '208px'" class="aside">
      <div class="brand">
        <span v-if="collapsed" class="brand-mark">ATS</span>
        <template v-else>
          <span class="brand-mark">ATS</span>
          <span class="brand-name">招聘管理</span>
        </template>
      </div>
      <el-menu :default-active="activeMenu" :collapse="collapsed" router class="menu">
        <el-menu-item index="/positions">
          <el-icon><Briefcase /></el-icon>
          <template #title>岗位管理</template>
        </el-menu-item>
        <el-menu-item index="/candidates">
          <el-icon><User /></el-icon>
          <template #title>候选人管理</template>
        </el-menu-item>
        <el-menu-item index="/applications">
          <el-icon><Tickets /></el-icon>
          <template #title>投递列表</template>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><DataAnalysis /></el-icon>
          <template #title>汇总导出</template>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <template #title>系统设置</template>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <el-button text class="fold-btn" @click="collapsed = !collapsed">
          <el-icon :size="18"><Expand v-if="collapsed" /><Fold v-else /></el-icon>
        </el-button>

        <nav class="indicators">
          <button
            v-for="item in quickStats"
            :key="item.label"
            class="indicator"
            :class="{ 'is-todo': item.todo && item.value > 0 }"
            type="button"
            @click="router.push(item.to)"
          >
            <span class="indicator-value">{{ item.value ?? '–' }}</span>
            <span class="indicator-label">{{ item.label }}</span>
          </button>
        </nav>

        <div class="right">
          <el-radio-group :model-value="theme" size="small" @change="applyTheme">
            <el-radio-button v-for="t in THEMES" :key="t.value" :value="t.value">{{ t.label }}</el-radio-button>
          </el-radio-group>
          <el-dropdown @command="logout">
            <span class="user">
              <el-icon><User /></el-icon>
              {{ auth.user.value?.username || '用户' }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  height: 100%;
}

/* ---- 侧栏 ---- */
.aside {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  transition: width 0.2s;
  overflow: hidden;
}
.brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
  padding: 0 var(--ats-sp-4);
  border-bottom: 1px solid var(--el-border-color-light);
  white-space: nowrap;
}
.brand-mark {
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-bold);
  letter-spacing: 0.04em;
  color: var(--el-color-primary);
}
.brand-name {
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-regular);
}
.menu {
  border-right: none;
  padding: var(--ats-sp-2) 0;
}
/* 当前项：左侧一条主色竖条标出，而不是整块高亮 */
.menu :deep(.el-menu-item) {
  height: 42px;
  line-height: 42px;
  margin: 2px var(--ats-sp-2);
  border-radius: var(--ats-radius-sm);
  position: relative;
}
.menu :deep(.el-menu-item.is-active) {
  background: var(--el-color-primary-light-9);
  font-weight: var(--ats-fw-medium);
}
.menu :deep(.el-menu-item.is-active)::before {
  content: '';
  position: absolute;
  left: 0;
  top: 9px;
  bottom: 9px;
  width: 3px;
  border-radius: 2px;
  background: var(--el-color-primary);
}

/* ---- 顶栏 ---- */
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  gap: var(--ats-sp-4);
  padding: 0 var(--ats-sp-4);
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}
.fold-btn {
  padding: 6px;
}
.indicators {
  flex: 1;
  display: flex;
  gap: var(--ats-sp-2);
}
/* 指标做成按钮：可点、有悬停反馈，让"待办"真的能点进去 */
.indicator {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 4px 10px;
  border: 1px solid transparent;
  border-radius: var(--ats-radius-sm);
  background: none;
  cursor: pointer;
  font-family: inherit;
  transition: background-color 0.15s, border-color 0.15s;
}
.indicator:hover {
  background: var(--el-fill-color-light);
}
.indicator:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 1px;
}
.indicator-value {
  font-size: 18px;
  font-weight: var(--ats-fw-bold);
  font-variant-numeric: var(--ats-nums);
  color: var(--el-text-color-primary);
  line-height: 1;
}
.indicator-label {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
/* 有待办时用提醒色，让「待 AI 筛选」有存在感 */
.indicator.is-todo .indicator-value {
  color: var(--el-color-warning);
}

.right {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-4);
}
.user {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-regular);
}

.main {
  background: var(--el-bg-color-page);
  padding: var(--ats-sp-4) var(--ats-sp-6);
}
</style>
