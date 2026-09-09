<!--
  【登录页】全屏居中的卡片：用户名 + 密码 + 登录按钮 + 「去注册」链接。
  登录成功 → 把 token 存进 auth → 跳到原来想去的页面（没有就去岗位管理）。
  失败 → 卡片里显示红字「用户名或密码错误」（不用全局弹窗，所以请求带了 silent）。
-->
<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { authApi } from '../api'
import { auth } from '../stores/auth'

const router = useRouter()
const route = useRoute()

const formRef = ref()
const form = reactive({ username: '', password: '' })
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}
const loading = ref(false)
const errorMsg = ref('')

async function submit() {
  await formRef.value.validate() // 必填没填会在输入框下面标红，并抛错终止
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await authApi.login(form.username, form.password)
    auth.setAuth(data.token, data.user)
    router.replace(route.query.redirect || { name: 'positions' })
  } catch (e) {
    errorMsg.value = e.response?.status === 401 ? '用户名或密码错误' : e.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <el-card class="auth-card" shadow="always">
      <h1 class="auth-title">ATS 招聘管理系统</h1>
      <p class="auth-sub">登录后管理岗位、候选人与招聘流程</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @keyup.enter="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" autofocus />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" show-password />
        </el-form-item>
        <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" class="auth-alert" />
        <el-button type="primary" :loading="loading" class="auth-btn" @click="submit">登 录</el-button>
      </el-form>
      <div class="auth-footer">
        还没有账号？<router-link to="/register">去注册</router-link>
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
