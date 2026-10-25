<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { portalAuthApi } from '../../api/portal'
import { STAGE_COLOR, STAGES } from '../../constants'
import { portalAuth } from '../../stores/portalAuth'

const router = useRouter()
const route = useRoute()

const formRef = ref()
const form = reactive({ phone: '', password: '' })
const rules = {
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '请输入 11 位手机号', trigger: 'blur' },
  ],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const loading = ref(false)
const errorMsg = ref('')

async function submit() {
  await formRef.value.validate()
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await portalAuthApi.login(form.phone.trim(), form.password)
    portalAuth.setAuth(data.token, data.user, data.candidate)
    router.replace(route.query.redirect || { name: 'portal-positions' })
  } catch (e) {
    errorMsg.value = e.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="portal-login">
    <div class="login-card">
      <div class="login-brand">ATS</div>
      <p class="login-sub">候选人登录 · 查看岗位与招聘进度</p>

      <div class="mini-pipeline" aria-hidden="true">
        <i v-for="s in STAGES" :key="s.value" :style="{ background: STAGE_COLOR[s.value] }" />
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        size="large"
        @keyup.enter="submit"
      >
        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="form.phone"
            name="phone"
            autocomplete="tel"
            inputmode="tel"
            maxlength="11"
            placeholder="请输入手机号"
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
          登 录
        </el-button>
      </el-form>

      <p class="login-hint">
        初始密码为 <b>admin</b>。手机号由 HR 录入系统后才能登录；如果提示「未找到你的档案」，请联系 HR。
      </p>

      <div class="login-footer">
        <span class="muted">简历由 HR 上传，你可以在「文件」里查看。</span>
        <router-link to="/login">我是 HR →</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mini-pipeline {
  display: flex;
  gap: 4px;
  margin: 0 0 var(--ats-sp-6);
}
.mini-pipeline i {
  height: 4px;
  flex: 1;
  border-radius: 2px;
  opacity: 0.85;
}
.login-alert {
  margin-bottom: var(--ats-sp-3);
}
.login-btn {
  width: 100%;
}
.login-footer a {
  color: var(--el-color-primary);
  text-decoration: none;
  white-space: nowrap;
}
.login-footer {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
</style>
