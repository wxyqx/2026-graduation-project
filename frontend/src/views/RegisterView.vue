<!--
  【注册页】用户名 + 密码 + 确认密码。
  用户名重复 → 后端回 409 → 显示「用户名已存在」。
  成功 → 后端顺手发了 token → 直接登录进后台，不用再登一次。
-->
<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { authApi } from '../api'
import { auth } from '../stores/auth'

const router = useRouter()

const formRef = ref()
const form = reactive({ username: '', password: '', confirm: '' })
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名 2～50 个字', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再输一次密码', trigger: 'blur' },
    {
      // 自定义校验：两次密码要一样
      validator: (_rule, value, callback) =>
        value === form.password ? callback() : callback(new Error('两次输入的密码不一致')),
      trigger: 'blur',
    },
  ],
}
const loading = ref(false)
const errorMsg = ref('')

async function submit() {
  await formRef.value.validate()
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await authApi.register(form.username, form.password)
    auth.setAuth(data.token, data.user)
    router.replace({ name: 'positions' })
  } catch (e) {
    errorMsg.value = e.response?.status === 409 ? '用户名已存在，换一个吧' : e.detail || '注册失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="always">
      <h1 class="auth-title">注册账号</h1>
      <p class="auth-sub">自用系统，只需用户名和密码</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @keyup.enter="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="2～50 个字" autofocus />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="至少 6 位" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="再输一次" show-password />
        </el-form-item>
        <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" class="auth-alert" />
        <el-button type="primary" :loading="loading" class="auth-btn" @click="submit">注册并登录</el-button>
      </el-form>
      <div class="auth-footer">
        已有账号？<router-link to="/login">去登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--el-bg-color-page);
}
.auth-card {
  width: 380px;
  padding: 8px 8px 0;
}
.auth-title {
  margin: 0;
  text-align: center;
  font-size: 22px;
}
.auth-sub {
  margin: 6px 0 22px;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.auth-alert {
  margin-bottom: 14px;
}
.auth-btn {
  width: 100%;
}
.auth-footer {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
