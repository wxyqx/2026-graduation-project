<!--
  【统一登录页】三端共用一个界面：
    · 整页渐变背景（不再左右分栏）
    · 7 关管线视觉与毛玻璃登录卡收在同一个居中组合里
    · 角色决定调用哪个登录接口、登录后跳哪个端
-->
<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { authApi } from '../api'
import { portalAuthApi } from '../api/portal'
import { techAuthApi } from '../api/tech'
import { STAGES } from '../constants'
import { auth } from '../stores/auth'
import { portalAuth } from '../stores/portalAuth'
import { techAuth } from '../stores/techAuth'

const route = useRoute()
const router = useRouter()

const ROLES = [
  { value: 'hr', label: 'HR' },
  { value: 'candidate', label: '候选人' },
  { value: 'tech', label: '技术管理' },
]

const role = ref(route.meta.loginRole || 'hr')
const formRef = ref()
const form = reactive({ account: '', password: '' })
const loading = ref(false)
const errorMsg = ref('')

const isCandidate = computed(() => role.value === 'candidate')
const roleLabel = computed(() => ROLES.find((r) => r.value === role.value)?.label || 'HR')

const rules = computed(() => ({
  account: isCandidate.value
    ? [
        { required: true, message: '请输入手机号', trigger: 'blur' },
        { pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位手机号', trigger: 'blur' },
      ]
    : [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}))

const hint = computed(() => {
  if (role.value === 'candidate') return '手机号由 HR 录入系统；初始密码为 admin。'
  if (role.value === 'tech') return '技术管理员账号由部署脚本或技术端创建。'
  return 'HR 账号由技术管理端创建，也可以在注册页自助注册。'
})

const accountPlaceholder = computed(() =>
  isCandidate.value ? '请输入手机号' : role.value === 'tech' ? '技术管理员用户名' : 'HR 用户名',
)

watch(
  () => route.meta.loginRole,
  (value) => {
    if (value && value !== role.value) {
      role.value = value
      resetFields()
    }
  },
)

function resetFields() {
  form.account = ''
  form.password = ''
  errorMsg.value = ''
  formRef.value?.clearValidate?.()
}

function switchRole(next) {
  if (next === role.value) return
  role.value = next
  resetFields()
}

async function submit() {
  await formRef.value.validate()
  loading.value = true
  errorMsg.value = ''
  try {
    if (role.value === 'candidate') {
      const data = await portalAuthApi.login(form.account.trim(), form.password)
      portalAuth.setAuth(data.token, data.user, data.candidate)
      router.replace(route.query.redirect || { name: 'portal-positions' })
    } else if (role.value === 'tech') {
      const data = await techAuthApi.login(form.account.trim(), form.password)
      techAuth.setAuth(data.token, data.user)
      router.replace(route.query.redirect || { name: 'tech-overview' })
    } else {
      const data = await authApi.login(form.account.trim(), form.password)
      auth.setAuth(data.token, data.user)
      router.replace(route.query.redirect || { name: 'positions' })
    }
  } catch (e) {
    errorMsg.value = e.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-content">
      <!-- 左：7 关管线视觉 -->
      <section class="login-hero" aria-hidden="true">
        <div class="hero-brand">ATS</div>
        <div class="hero-role">招聘管理系统 · 三端统一入口</div>

        <ol class="hero-pipeline">
          <li v-for="(s, i) in STAGES" :key="s.value" class="hero-stop">
            <span class="hero-bar" :style="{ width: `${70 - i * 8}%` }" />
            <span class="hero-label">{{ s.label }}</span>
          </li>
        </ol>

        <p class="hero-note">一条投递要走的 7 关</p>
      </section>

      <!-- 右：毛玻璃登录卡 -->
      <main class="login-main">
        <div class="login-card">
          <div class="card-head">
            <div class="card-brand">ATS <span>登录</span></div>
            <p class="card-sub">选择身份后登录，进入对应的工作台</p>
          </div>

          <div class="role-tabs" role="tablist" aria-label="选择登录身份">
            <button
              v-for="r in ROLES"
              :key="r.value"
              type="button"
              class="role-tab"
              :class="{ active: role === r.value }"
              role="tab"
              :aria-selected="role === r.value"
              @click="switchRole(r.value)"
            >
              {{ r.label }}
            </button>
          </div>

          <el-form
            ref="formRef"
            :model="form"
            :rules="rules"
            label-position="top"
            size="large"
            @keyup.enter="submit"
          >
            <el-form-item :label="isCandidate ? '手机号' : '用户名'" prop="account">
              <el-input
                v-model="form.account"
                :name="isCandidate ? 'phone' : 'username'"
                :autocomplete="isCandidate ? 'tel' : 'username'"
                :inputmode="isCandidate ? 'tel' : undefined"
                :maxlength="isCandidate ? 11 : 50"
                :placeholder="accountPlaceholder"
                autofocus
              />
            </el-form-item>
            <el-form-item label="密码" prop="password">
              <el-input
                v-model="form.password"
                name="password"
                autocomplete="current-password"
                type="password"
                placeholder="请输入密码"
                show-password
              />
            </el-form-item>

            <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" class="login-alert" />

            <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="submit">
              登录 {{ roleLabel }}
            </el-button>
          </el-form>

          <p class="login-hint">{{ hint }}</p>

          <div class="login-footer">
            <template v-if="role === 'hr'">
              <router-link to="/register">注册 HR 账号</router-link>
              <span class="footer-dot">·</span>
              <span>候选人请切换上方身份</span>
            </template>
            <template v-else-if="role === 'candidate'">
              <span>账号问题请联系 HR</span>
              <span class="footer-dot">·</span>
              <span>简历由 HR 上传</span>
            </template>
            <template v-else>
              <span>仅限技术维护人员使用</span>
              <span class="footer-dot">·</span>
              <span>其他身份请切换上方页签</span>
            </template>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
/* ============================================================
   整页渐变背景
   ============================================================ */
.login-page {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  box-sizing: border-box;
  overflow: hidden;
  background:
    radial-gradient(circle at 14% 16%, rgb(95 211 198 / 20%), transparent 40%),
    radial-gradient(circle at 86% 82%, rgb(46 129 122 / 28%), transparent 46%),
    linear-gradient(135deg, #041a18 0%, #082925 38%, #0d3a36 66%, #051816 100%);
}
.login-page::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgb(255 255 255 / 3%) 1px, transparent 1px);
  background-size: 100% 48px;
  mask-image: linear-gradient(to bottom, transparent, #000 18%, #000 82%, transparent);
  pointer-events: none;
}
.login-page::after {
  content: '';
  position: absolute;
  width: 520px;
  height: 520px;
  right: -180px;
  top: -180px;
  border-radius: 50%;
  background: radial-gradient(circle, rgb(95 211 198 / 14%), transparent 68%);
  pointer-events: none;
}

/* 管线 + 登录卡：同一个居中组合，不再左右分栏 */
.login-content {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1120px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 400px;
  gap: 64px;
  align-items: center;
}

/* ============================================================
   左侧 7 关管线
   ============================================================ */
.login-hero {
  color: #dcefeb;
}
.hero-brand {
  font-size: 44px;
  font-weight: 700;
  letter-spacing: 0.1em;
  line-height: 1;
  color: #bff3ea;
}
.hero-role {
  margin-top: 8px;
  font-size: 13px;
  color: rgb(220 239 235 / 58%);
  letter-spacing: 0.04em;
}
.hero-pipeline {
  list-style: none;
  margin: 34px 0 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.hero-stop {
  display: flex;
  align-items: center;
  gap: 16px;
}
.hero-bar {
  height: 7px;
  border-radius: 999px;
  flex: none;
  background: linear-gradient(90deg, rgb(46 129 122 / 30%) 0%, #5fc4ba 45%, #c9fff7 100%);
  box-shadow: 0 0 20px rgb(105 220 207 / 18%);
}
.hero-label {
  font-size: 13px;
  color: rgb(220 239 235 / 76%);
  white-space: nowrap;
}
.hero-note {
  margin: 28px 0 0;
  font-size: 12px;
  color: rgb(220 239 235 / 34%);
  letter-spacing: 0.04em;
}

/* ============================================================
   右侧毛玻璃登录卡
   ============================================================ */
.login-main {
  display: flex;
  justify-content: center;
}
.login-card {
  width: 100%;
  max-width: 400px;
  padding: 30px;
  box-sizing: border-box;
  border-radius: 20px;
  border: 1px solid rgb(255 255 255 / 20%);
  background: linear-gradient(160deg, rgb(255 255 255 / 15%), rgb(255 255 255 / 6%));
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  box-shadow:
    0 24px 70px rgb(0 0 0 / 38%),
    inset 0 1px 0 rgb(255 255 255 / 18%);
  color: #eaf7f4;
}
.card-brand {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 0.08em;
  background: linear-gradient(90deg, #f0fffc, #8fe8de);
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
.card-brand span {
  font-size: 13px;
  font-weight: 400;
  letter-spacing: 0;
  color: rgb(234 247 244 / 58%);
  margin-left: 6px;
  -webkit-text-fill-color: rgb(234 247 244 / 58%);
}
.card-sub {
  margin: 4px 0 22px;
  font-size: 13px;
  color: rgb(234 247 244 / 52%);
}

/* 身份切换：玻璃胶囊 */
.role-tabs {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 2px;
  padding: 3px;
  margin-bottom: 22px;
  background: rgb(255 255 255 / 7%);
  border: 1px solid rgb(255 255 255 / 12%);
  border-radius: 11px;
}
.role-tab {
  border: 0;
  background: transparent;
  padding: 8px 4px;
  border-radius: 9px;
  font: inherit;
  font-size: 13px;
  color: rgb(234 247 244 / 58%);
  cursor: pointer;
  transition: background-color 0.15s, color 0.15s, box-shadow 0.15s;
}
.role-tab:hover {
  color: #d8fff8;
}
.role-tab.active {
  background: rgb(255 255 255 / 16%);
  color: #f4fffd;
  font-weight: 600;
  box-shadow: 0 1px 6px rgb(0 0 0 / 18%), inset 0 1px 0 rgb(255 255 255 / 16%);
}
.role-tab:focus-visible {
  outline: 2px solid #8fe8de;
  outline-offset: 1px;
}

/* 表单在玻璃卡里的配色 */
.login-card :deep(.el-form-item__label) {
  color: rgb(234 247 244 / 72%);
  font-weight: 400;
}
.login-card :deep(.el-input__wrapper) {
  background: rgb(255 255 255 / 8%);
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 17%);
  border-radius: 10px;
}
.login-card :deep(.el-input__wrapper:hover) {
  box-shadow: inset 0 0 0 1px rgb(255 255 255 / 28%);
}
.login-card :deep(.el-input__wrapper.is-focus) {
  box-shadow:
    inset 0 0 0 1px rgb(143 232 222 / 75%),
    0 0 0 3px rgb(95 211 198 / 12%);
}
.login-card :deep(.el-input__inner) {
  color: #f4fffd;
}
.login-card :deep(.el-input__inner::placeholder) {
  color: rgb(234 247 244 / 34%);
}
.login-card :deep(.el-input__password) {
  color: rgb(234 247 244 / 48%);
}
.login-card :deep(.el-alert) {
  background: rgb(180 80 74 / 16%);
  border: 1px solid rgb(255 150 140 / 24%);
}
.login-card :deep(.el-alert__title) {
  color: #ffd9d5;
}

.login-alert {
  margin-bottom: 14px;
}
.login-btn {
  width: 100%;
  border: 0;
  color: #04211f;
  font-weight: 600;
  background: linear-gradient(135deg, #a9f1e7 0%, #5fd3c6 45%, #2e817a 100%);
  box-shadow: 0 12px 28px rgb(46 129 122 / 32%);
}
.login-btn:hover {
  background: linear-gradient(135deg, #c9fff8 0%, #7fe0d4 45%, #3a958d 100%);
  color: #04211f;
}
.login-hint {
  margin: 16px 0 0;
  font-size: 12px;
  line-height: 1.6;
  color: rgb(234 247 244 / 36%);
}
.login-footer {
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px solid rgb(255 255 255 / 12%);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
  color: rgb(234 247 244 / 42%);
}
.login-footer a {
  color: #a9f1e7;
  text-decoration: none;
}
.footer-dot {
  color: rgb(234 247 244 / 22%);
}

/* ============================================================
   窄屏：上下排列，背景仍是整页渐变
   ============================================================ */
@media (max-width: 980px) {
  .login-page {
    padding: 32px 20px;
    align-items: flex-start;
  }
  .login-content {
    grid-template-columns: minmax(0, 1fr);
    gap: 28px;
    max-width: 440px;
  }
  .hero-brand {
    font-size: 34px;
  }
  .hero-role {
    font-size: 12px;
  }
  .hero-pipeline {
    margin-top: 22px;
    gap: 9px;
  }
  .hero-bar {
    height: 5px;
  }
  .hero-label {
    font-size: 11px;
  }
  .hero-note {
    display: none;
  }
  .login-main {
    justify-content: stretch;
  }
  .login-card {
    max-width: none;
    padding: 24px;
    border-radius: 18px;
  }
  .card-brand {
    font-size: 22px;
  }
}
</style>
