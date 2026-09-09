<!--
  【后台布局】登录后所有页面的「外框」：
    左边：可折叠的菜单（岗位管理 / 投递列表 / 汇总导出 / 系统设置）
    顶部：状态栏——5 个速览数字（来自 /stats/overview）+ 三档主题切换 + 用户名/退出
    中间：router-view，显示具体页面

  子页面改了数据（新建岗位、推进投递…）后想让顶部数字刷新，调 inject('refreshStats')() 即可。
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

// ---- 顶部速览数字 ----
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

const quickStats = computed(() => {
  const s = stats.value
  return [
    { label: '在招岗位', value: s?.position_count },
    { label: '进行中投递', value: s?.pending_count },
    { label: '待 AI 筛选', value: s?.ai_pending_count },
    { label: '本周进行', value: s?.week_in_progress },
    { label: '上周完成', value: s?.last_week_completed },
  ]
})

function logout() {
  auth.clear()
  router.replace({ name: 'login' })
}
</script>

<template>
  <el-container class="layout">
    <el-aside :width="collapsed ? '64px' : '200px'" class="aside">
      <div class="logo">{{ collapsed ? 'ATS' : 'ATS 招聘管理' }}</div>
      <el-menu :default-active="activeMenu" :collapse="collapsed" router class="menu">
        <el-menu-item index="/positions">
          <el-icon><Briefcase /></el-icon>
          <span>岗位管理</span>
        </el-menu-item>
        <el-menu-item index="/candidates">
          <el-icon><User /></el-icon>
          <span>候选人管理</span>
        </el-menu-item>
        <el-menu-item index="/applications">
          <el-icon><Tickets /></el-icon>
          <span>投递列表</span>
        </el-menu-item>
        <el-menu-item index="/stats">
          <el-icon><DataAnalysis /></el-icon>
          <span>汇总导出</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <el-button text class="fold-btn" @click="collapsed = !collapsed">
          <el-icon :size="18"><Expand v-if="collapsed" /><Fold v-else /></el-icon>
        </el-button>

        <div class="quick-stats">
          <div v-for="item in quickStats" :key="item.label" class="stat">
            <span class="stat-value">{{ item.value ?? '–' }}</span>
            <span class="stat-label">{{ item.label }}</span>
          </div>
        </div>

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
.aside {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  transition: width 0.2s;
  overflow: hidden;
}
.logo {
  height: 56px;
  line-height: 56px;
  text-align: center;
  font-weight: 600;
  font-size: 16px;
  color: var(--el-color-primary);
  border-bottom: 1px solid var(--el-border-color-light);
  white-space: nowrap;
}
.menu {
  border-right: none;
}
.topbar {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 16px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}
.fold-btn {
  padding: 6px;
}
.quick-stats {
  flex: 1;
  display: flex;
  gap: 28px;
}
.stat {
  display: flex;
  align-items: baseline;
  gap: 6px;
}
.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--el-color-primary);
}
.stat-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.right {
  display: flex;
  align-items: center;
  gap: 18px;
}
.user {
  display: flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font-size: 14px;
  color: var(--el-text-color-regular);
}
.main {
  background: var(--el-bg-color-page);
}
</style>
