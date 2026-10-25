<!--
  【注册页】与候选人登录页同一套视觉：柔和渐变背景上居中一张圆角卡片，
  卡片顶部一条 7 关迷你色条点题。样式复用 portal.css 的全局类。
-->
<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { authApi } from '../api'
import { STAGES, STAGE_COLOR } from '../constants'
import { auth } from '../stores/auth'

const router = useRouter()

const formRef = ref()
const form = reactive({ username: '', real_name: '', phone: '', password: '', confirm: '' })
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名 2～50 个字', trigger: 'blur' },
  ],
  phone: [
    { required: true, message: '请输入手机号', trigger: 'blur' },
    { pattern: /^1[3-9]\d{9}$/, message: '手机号 11 位，1 开头', trigger: 'blur' },
  ],
  real_name: [
    { required: true, message: '请输入实名', trigger: 'blur' },
    { min: 2, max: 50, message: '姓名 2～50 个字', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再输一次密码', trigger: 'blur' },
    {
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
    const data = await authApi.register(form.username, form.password, form.phone, form.real_name)
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
  <div class="portal-login">
    <div class="login-card">
      <div class="login-brand">ATS</div>
      <p class="login-sub">注册 HR 账号 · 实名、用户名、手机号和密码</p>

      <div class="mini-pipeline" aria-hidden="true">
        <i v-for="s in STAGES" :key="s.value" :style="{ background: STAGE_COLOR[s.value] }" />
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @keyup.enter="submit">
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            name="username"
            autocomplete="username"
            spellcheck="false"
            placeholder="2～50 个字"
            autofocus
          />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input
            v-model="form.phone"
            name="phone"
            autocomplete="tel"
            maxlength="11"
            placeholder="11 位手机号（必填）"
          />
        </el-form-item>
        <el-form-item label="姓名" prop="real_name">
          <el-input v-model="form.real_name" name="name" autocomplete="name" maxlength="50" placeholder="实名（必填）" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            name="password"
            autocomplete="new-password"
            type="password"
            placeholder="至少 6 位"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input
            v-model="form.confirm"
            name="confirm-password"
            autocomplete="new-password"
            type="password"
            placeholder="再输一次"
            show-password
          />
        </el-form-item>

        <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" class="login-alert" />

        <el-button type="primary" size="large" class="login-btn" :loading="loading" @click="submit">
          注册并登录
        </el-button>
      </el-form>

      <div class="login-footer">
        <router-link to="/login">已有账号？去登录</router-link>
        <span class="footer-links">
          <router-link to="/portal/login">我是候选人</router-link>
          <span class="footer-sep">·</span>
          <router-link to="/tech/login">技术管理</router-link>
        </span>
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
.login-footer {
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}
.login-footer a {
  color: var(--el-color-primary);
  text-decoration: none;
  white-space: nowrap;
}
.footer-links {
  display: flex;
  align-items: center;
  gap: 6px;
}
.footer-sep {
  color: var(--el-text-color-placeholder);
}
</style>
