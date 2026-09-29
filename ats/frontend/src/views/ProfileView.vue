<!--
  【个人信息页】点右上角用户名 →「个人信息」进来的地方。
  两件事：
    1. 改用户名（登录时用的名字，顶栏显示的就是它）
    2. 改密码 —— 必须填「当前密码」验证是本人，否则拿到 token 的人能直接把密码改掉
  用户名和密码可以一起改，也可以只改一项（密码三项留空 = 不改密码）。
  保存成功后后端会重发一张 token，这里替换本地登录状态，顶栏名字立刻更新。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, reactive, ref } from 'vue'

import { authApi } from '../api'
import { auth } from '../stores/auth'

const formRef = ref()
const saving = ref(false)
const form = reactive({ username: '', current_password: '', new_password: '', confirm_password: '' })
// 进页面时把当前用户名填进去，方便在原文上改
form.username = auth.user.value?.username || ''

// 注册时间只读展示（后端返回的 ISO 时间简单截断成「年-月-日 时:分」）
const createTime = computed(() => {
  const t = auth.user.value?.create_time
  return t ? String(t).replace('T', ' ').slice(0, 16) : '—'
})

// 新密码 / 确认密码只在「填了内容」时校验，留空代表不改密码
const rules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名 2～50 个字', trigger: 'blur' },
  ],
  new_password: [
    {
      validator: (_rule, value, callback) =>
        value && value.length < 6 ? callback(new Error('新密码至少 6 位')) : callback(),
      trigger: 'blur',
    },
  ],
  confirm_password: [
    {
      validator: (_rule, value, callback) =>
        value && value !== form.new_password ? callback(new Error('两次输入的新密码不一致')) : callback(),
      trigger: 'blur',
    },
  ],
}

async function save() {
  await formRef.value.validate()
  // 要改密码就必须先验当前密码
  if (form.new_password && !form.current_password) {
    ElMessage.warning('修改密码请先输入当前密码')
    return
  }

  const payload = { username: form.username }
  if (form.new_password) {
    payload.current_password = form.current_password
    payload.new_password = form.new_password
  }

  saving.value = true
  try {
    const d = await authApi.updateProfile(payload)
    auth.setAuth(d.token, d.user) // 新 token + 新用户名一起替换
    form.current_password = ''
    form.new_password = ''
    form.confirm_password = ''
    ElMessage.success('个人信息已更新')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>个人信息</h2>
    </div>

    <el-card shadow="never" class="profile-card">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            name="username"
            autocomplete="username"
            maxlength="50"
            placeholder="2～50 个字，登录时用它"
          />
        </el-form-item>

        <el-form-item label="注册时间">
          <span class="muted">{{ createTime }}</span>
        </el-form-item>

        <div class="section-title">
          修改密码
          <span class="muted">（不修改请留空）</span>
        </div>

        <el-form-item label="当前密码" prop="current_password">
          <el-input
            v-model="form.current_password"
            type="password"
            name="current-password"
            autocomplete="current-password"
            show-password
            maxlength="72"
            placeholder="验证是本人操作"
          />
        </el-form-item>

        <el-form-item label="新密码" prop="new_password">
          <el-input
            v-model="form.new_password"
            type="password"
            name="new-password"
            autocomplete="new-password"
            show-password
            maxlength="72"
            placeholder="至少 6 位"
          />
        </el-form-item>

        <el-form-item label="确认新密码" prop="confirm_password">
          <el-input
            v-model="form.confirm_password"
            type="password"
            name="confirm-password"
            autocomplete="new-password"
            show-password
            maxlength="72"
            placeholder="再输一遍新密码"
          />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" :loading="saving" @click="save">保存修改</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.profile-card {
  max-width: 520px;
}
/* 密码分区的小标题：和上面「用户名」拉开一点，说明下面这组是可选的 */
.section-title {
  margin: 6px 0 16px;
  padding-top: 14px;
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: var(--ats-fs-body);
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
</style>
