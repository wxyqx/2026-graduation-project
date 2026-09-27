<!--
  【登录页】全屏两栏：左边是「招聘管线」的产品视觉，右边是登录表单。

  设计说明（v3.12）：让"进门第一眼"就点题 —— 左边竖排 7 个阶段色条，
  深浅就是系统的核心结构；右边是安静的登录卡。不再是居中的单卡片。
-->
<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { authApi } from '../api'
import { STAGES, STAGE_COLOR } from '../constants'
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
  await formRef.value.validate()
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
    <!-- 左：管线视觉 -->
    <aside class="auth-art">
      <div class="art-brand">ATS</div>
      <ol class="art-pipeline">
        <li v-for="s in STAGES" :key="s.value" class="art-stop">
          <i class="art-bar" :style="{ background: STAGE_COLOR[s.value] }" />
          <span class="art-name">{{ s.label }}</span>
        </li>
      </ol>
      <p class="art-note">一条投递要走的 7 关</p>
    </aside>

    <!-- 右：登录表单 -->
    <main class="auth-main">
      <div class="auth-box">
        <h1>登录</h1>
        <p class="auth-sub">管理岗位、候选人与招聘流程</p>
        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" size="large" @keyup.enter="submit">
          <el-form-item label="用户名" prop="username">
            <el-input
              v-model="form.username"
              name="username"
              autocomplete="username"
              spellcheck="false"
              placeholder="请输入用户名"
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
          <el-alert v-if="errorMsg" :title="errorMsg" type="error" show-icon :closable="false" class="auth-alert" />
          <el-button type="primary" :loading="loading" class="auth-btn" @click="submit">登 录</el-button>
        </el-form>
        <div class="auth-footer">
          还没有账号？<router-link to="/register">去注册</router-link>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100%;
  display: grid;
  grid-template-columns: minmax(280px, 34%) minmax(0, 1fr);
}

/* ---- 左侧管线视觉 ---- */
.auth-art {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color-light);
  padding: var(--ats-sp-8) var(--ats-sp-6);
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: var(--ats-sp-4);
}
.art-brand {
  font-size: 30px;
  font-weight: var(--ats-fw-bold);
  letter-spacing: 0.08em;
  color: var(--el-color-primary);
}
.art-pipeline {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.art-stop {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
/* 竖条宽度随关卡递增，深浅与宽窄双重表达"越走越深" */
.art-bar {
  height: 6px;
  border-radius: 3px;
}
.art-stop:nth-child(1) .art-bar { width: 20%; }
.art-stop:nth-child(2) .art-bar { width: 28%; }
.art-stop:nth-child(3) .art-bar { width: 36%; }
.art-stop:nth-child(4) .art-bar { width: 44%; }
.art-stop:nth-child(5) .art-bar { width: 52%; }
.art-stop:nth-child(6) .art-bar { width: 60%; }
.art-stop:nth-child(7) .art-bar { width: 68%; }
.art-stop:nth-child(8) .art-bar { width: 76%; }
.art-name {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}
.art-note {
  margin: 0;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
}

/* ---- 右侧表单 ---- */
.auth-main {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--ats-sp-6);
}
.auth-box {
  width: 360px;
  max-width: 100%;
}
.auth-box h1 {
  margin: 0;
  font-size: 24px;
  font-weight: var(--ats-fw-bold);
}
.auth-sub {
  margin: 6px 0 24px;
  color: var(--el-text-color-secondary);
  font-size: var(--ats-fs-note);
}
.auth-alert {
  margin-bottom: var(--ats-sp-3);
}
.auth-btn {
  width: 100%;
}
.auth-footer {
  margin-top: var(--ats-sp-4);
  text-align: center;
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-secondary);
}

/* 窄屏：左栏的管线视觉先让位，登录表单占满整宽（不留两栏挤成一条） */
@media (max-width: 900px) {
  .auth-page {
    grid-template-columns: minmax(0, 1fr);
  }
  .auth-art {
    display: none;
  }
  .auth-main {
    padding: var(--ats-sp-4);
  }
}
</style>
