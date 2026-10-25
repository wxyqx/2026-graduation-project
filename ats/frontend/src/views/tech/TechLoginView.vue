<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { techAuthApi } from '../../api/tech'
import { techAuth } from '../../stores/techAuth'

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
  await formRef.value.validate()
  loading.value = true
  errorMsg.value = ''
  try {
    const data = await techAuthApi.login(form.username.trim(), form.password)
    techAuth.setAuth(data.token, data.user)
    router.replace(route.query.redirect || { name: 'tech-overview' })
  } catch (e) {
    errorMsg.value = e.detail || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="tech-login">
    <div class="tech-login-card">
      <div class="brand">ATS <span>技术管理</span></div>
      <p class="sub">系统维护入口：账号、配置、日志、备份</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @keyup.enter="submit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="技术管理员用户名" autocomplete="username" autofocus />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="密码" autocomplete="current-password" />
        </el-form-item>
        <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" class="err" />
        <el-button type="primary" size="large" class="btn" :loading="loading" @click="submit">登 录</el-button>
      </el-form>
      <p class="hint">
        初始账号由部署脚本创建：<code>scripts/create_user.py --role admin</code>。
        这不是 HR 入口，也不是候选人入口。
      </p>
      <div class="links">
        <router-link to="/login">HR 登录</router-link>
        <router-link to="/portal/login">候选人登录</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tech-login {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ats-sp-4);
  background:
    radial-gradient(circle at 80% 10%, var(--el-color-primary-light-9), transparent 45%),
    var(--el-bg-color-page);
  box-sizing: border-box;
}
.tech-login-card {
  width: 100%;
  max-width: 420px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 16px;
  padding: var(--ats-sp-6);
  box-shadow: 0 10px 40px rgb(15 111 104 / 10%);
  box-sizing: border-box;
}
.brand {
  font-size: 26px;
  font-weight: var(--ats-fw-bold);
  letter-spacing: 0.08em;
  color: var(--el-color-primary);
}
.brand span {
  font-size: var(--ats-fs-note);
  letter-spacing: 0;
  color: var(--el-text-color-secondary);
  font-weight: var(--ats-fw-normal);
}
.sub {
  margin: 4px 0 var(--ats-sp-6);
  color: var(--el-text-color-secondary);
  font-size: var(--ats-fs-note);
}
.err {
  margin-bottom: var(--ats-sp-3);
}
.btn {
  width: 100%;
}
.hint {
  margin: var(--ats-sp-4) 0 0;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
  line-height: 1.6;
}
.hint code {
  color: var(--el-text-color-secondary);
}
.links {
  display: flex;
  gap: var(--ats-sp-4);
  margin-top: var(--ats-sp-3);
  padding-top: var(--ats-sp-3);
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: var(--ats-fs-label);
}
.links a {
  color: var(--el-color-primary);
  text-decoration: none;
}
</style>
