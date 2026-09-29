<!--
  【个人信息弹窗】点右上角用户名 →「个人信息」弹出。
  用弹窗而不是整页：这里只有四项内容，单独占一页太空；弹窗既不打断当前工作，也放得下。

  两件事：
    1. 改用户名（登录时用的名字，顶栏显示的就是它）
    2. 改密码 —— 必须填「当前密码」验证是本人，否则拿到 token 的人能直接把密码改掉
  用户名和密码可以一起改，也可以只改一项（密码三项留空 = 不改密码）。
  保存成功后后端会重发一张 token，这里替换本地登录状态，顶栏名字立刻更新。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, reactive, ref, watch } from 'vue'

import { authApi } from '../api'
import { auth } from '../stores/auth'

const props = defineProps({ modelValue: { type: Boolean, default: false } })
const emit = defineEmits(['update:modelValue'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const formRef = ref()
const saving = ref(false)
const form = reactive({ username: '', current_password: '', new_password: '', confirm_password: '' })

// 头像里的首字母 + 注册时间，给弹窗一个「这是谁」的落点，不至于一上来就是四个空输入框
const initial = computed(() => (auth.user.value?.username || 'U').slice(0, 1).toUpperCase())
const createTime = computed(() => {
  const t = auth.user.value?.create_time
  return t ? String(t).replace('T', ' ').slice(0, 16) : '—'
})

// 打开时按当前账号重置表单，避免上次残留。immediate 兼顾「一挂载就是打开状态」的情况
function fillForm() {
  form.username = auth.user.value?.username || ''
  form.current_password = ''
  form.new_password = ''
  form.confirm_password = ''
  formRef.value?.clearValidate()
}
watch(visible, (v) => v && fillForm(), { immediate: true })

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
    visible.value = false
    ElMessage.success('个人信息已更新')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    title="个人信息"
    class="ats-dialog-narrow"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <!-- 身份抬头：换谁进来都先看到「这是谁」，下面才是可改的字段 -->
    <div class="identity">
      <div class="avatar">{{ initial }}</div>
      <div class="who">
        <div class="who-name">{{ auth.user.value?.username || '用户' }}</div>
        <div class="muted">注册于 {{ createTime }}</div>
      </div>
    </div>

    <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="form.username"
          name="username"
          autocomplete="username"
          maxlength="50"
          placeholder="2～50 个字，登录时用它"
        />
      </el-form-item>

      <div class="section">
        <span>修改密码</span>
        <span class="muted">不需要修改请留空</span>
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
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存修改</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.identity {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
  padding: var(--ats-sp-3) var(--ats-sp-4);
  border-radius: var(--ats-radius);
  background: var(--el-fill-color-lighter);
  margin-bottom: var(--ats-sp-4);
}
.avatar {
  width: 44px;
  height: 44px;
  flex: none;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-bold);
}
.who-name {
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
  line-height: 1.3;
}
/* 密码分区的小标题：用细线把「必填的用户名」和「可选的改密码」分开 */
.section {
  display: flex;
  align-items: baseline;
  gap: var(--ats-sp-2);
  margin: var(--ats-sp-1) 0 var(--ats-sp-3);
  padding-top: var(--ats-sp-3);
  border-top: 1px solid var(--el-border-color-lighter);
  font-size: var(--ats-fs-body);
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
</style>
