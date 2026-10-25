<!--
  【技术管理端布局】只做系统维护：概览 / 账号 / 系统配置 / 日志 / 备份。
  与 HR 端视觉同源（同一套主题变量），但不展示任何招聘业务菜单。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { techAuthApi } from '../api/tech'
import { techAuth } from '../stores/techAuth'
import { THEMES, applyTheme, theme } from '../theme'
import UserAvatar from '../components/UserAvatar.vue'

const route = useRoute()
const router = useRouter()

const pwdVisible = ref(false)
const pwdRef = ref()
const pwdLoading = ref(false)
const pwdForm = reactive({ current_password: '', new_password: '', confirm: '' })
const pwdRules = {
  current_password: [{ required: true, message: '请输入当前密码', trigger: 'blur' }],
  new_password: [
    { required: true, message: '请输入新密码', trigger: 'blur' },
    { min: 6, message: '至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再输入一次', trigger: 'blur' },
    {
      validator: (_r, v, cb) => (v === pwdForm.new_password ? cb() : cb(new Error('两次输入不一致'))),
      trigger: 'blur',
    },
  ],
}

function openPassword() {
  pwdForm.current_password = ''
  pwdForm.new_password = ''
  pwdForm.confirm = ''
  pwdVisible.value = true
}

async function submitPassword() {
  await pwdRef.value.validate()
  pwdLoading.value = true
  try {
    const data = await techAuthApi.changePassword(pwdForm.current_password, pwdForm.new_password)
    techAuth.setAuth(data.token, data.user)
    ElMessage.success('密码已修改')
    pwdVisible.value = false
  } finally {
    pwdLoading.value = false
  }
}

const menu = [
  { path: '/tech', label: '运行概览', icon: 'DataAnalysis' },
  { path: '/tech/accounts', label: '账号管理', icon: 'UserFilled' },
  { path: '/tech/candidate-owners', label: '候选人负责人', icon: 'Avatar' },
  { path: '/tech/stage-owners', label: '关卡负责人', icon: 'Files' },
  { path: '/tech/config', label: '系统配置', icon: 'Setting' },
  { path: '/tech/logs', label: '操作日志', icon: 'List' },
  { path: '/tech/backup', label: '备份导出', icon: 'Download' },
]

async function refreshMe() {
  try {
    const user = await techAuthApi.me()
    techAuth.setUser(user)
  } catch {
    /* 401 拦截器处理 */
  }
}

function onUserCommand(command) {
  if (command === 'logout') {
    techAuth.clear()
    router.replace({ name: 'tech-login' })
  } else if (command === 'hr') {
    window.location.href = '/'
  } else if (command === 'portal') {
    window.location.href = '/portal/login'
  } else if (command === 'password') {
    openPassword()
  }
}

onMounted(refreshMe)
</script>

<template>
  <el-container class="tech-layout">
    <el-aside width="210px" class="tech-aside">
      <div class="tech-brand">
        <span class="brand-mark">ATS</span>
        <span class="brand-sub">技术管理</span>
      </div>
      <el-menu :default-active="route.path" router class="tech-menu">
        <el-menu-item v-for="item in menu" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <template #title>{{ item.label }}</template>
        </el-menu-item>
      </el-menu>
      <div class="tech-aside-foot muted">仅系统维护 · 不展示招聘数据</div>
    </el-aside>

    <el-container>
      <el-header class="tech-header">
        <div class="tech-title">系统维护</div>
        <div class="tech-header-right">
          <el-radio-group :model-value="theme" size="small" @update:model-value="applyTheme">
            <el-radio-button v-for="t in THEMES" :key="t.value" :value="t.value">{{ t.label }}</el-radio-button>
          </el-radio-group>
          <el-dropdown trigger="click" @command="onUserCommand">
            <button type="button" class="tech-user">
              <UserAvatar
                :fetch-blob="techAuthApi.avatarBlob"
                :upload="techAuthApi.updateAvatar"
                editable
                :name="techAuth.displayName.value || '管理员'"
                :size="32"
              />
              <span>{{ techAuth.displayName.value }}</span>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="hr">返回 HR 端</el-dropdown-item>
                <el-dropdown-item command="portal">候选人端入口</el-dropdown-item>
                <el-dropdown-item command="password" divided>修改密码</el-dropdown-item>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main class="tech-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <el-dialog v-model="pwdVisible" title="修改密码" class="ats-dialog-narrow" append-to-body>
    <el-form ref="pwdRef" :model="pwdForm" :rules="pwdRules" label-position="top">
      <el-form-item label="当前密码" prop="current_password">
        <el-input v-model="pwdForm.current_password" type="password" show-password autocomplete="current-password" />
      </el-form-item>
      <el-form-item label="新密码" prop="new_password">
        <el-input v-model="pwdForm.new_password" type="password" show-password autocomplete="new-password" />
      </el-form-item>
      <el-form-item label="确认新密码" prop="confirm">
        <el-input v-model="pwdForm.confirm" type="password" show-password autocomplete="new-password" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="pwdVisible = false">取消</el-button>
      <el-button type="primary" :loading="pwdLoading" @click="submitPassword">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.tech-layout {
  height: 100%;
}
.tech-aside {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  display: flex;
  flex-direction: column;
}
.tech-brand {
  display: flex;
  align-items: baseline;
  gap: 6px;
  padding: 18px 20px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.brand-mark {
  font-size: 20px;
  font-weight: var(--ats-fw-bold);
  letter-spacing: 0.06em;
  color: var(--el-color-primary);
}
.brand-sub {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.tech-menu {
  border-right: 0;
  flex: 1;
}
.tech-aside-foot {
  padding: 12px 20px;
  font-size: var(--ats-fs-label);
  line-height: 1.5;
  border-top: 1px solid var(--el-border-color-lighter);
}
.tech-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 56px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color-light);
}
.tech-title {
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
}
.tech-header-right {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
}
.tech-user {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  background: transparent;
  color: var(--el-text-color-regular);
  font-size: var(--ats-fs-note);
  cursor: pointer;
}
.tech-main {
  background: var(--el-bg-color-page);
  padding: var(--ats-sp-4);
}
</style>
