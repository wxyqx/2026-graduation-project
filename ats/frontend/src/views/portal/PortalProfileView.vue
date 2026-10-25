<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { portalAuthApi } from '../../api/portal'
import { portalAuth } from '../../stores/portalAuth'
import { THEMES, applyTheme, theme } from '../../theme'
import UserAvatar from '../../components/UserAvatar.vue'

const router = useRouter()

const candidate = computed(() => portalAuth.candidate.value || {})
const user = computed(() => portalAuth.user.value || {})

// 头像换好后广播刷新（顶栏头像监听此事件）
function onAvatarUpdated() {
  window.dispatchEvent(new Event('avatar-updated'))
}

// ---- 改密 ----
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
      validator: (_rule, value, callback) =>
        value === pwdForm.new_password ? callback() : callback(new Error('两次输入不一致')),
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
    const data = await portalAuthApi.changePassword(pwdForm.current_password, pwdForm.new_password)
    portalAuth.setAuth(data.token, data.user, data.candidate)
    ElMessage.success('密码已修改')
    pwdVisible.value = false
  } catch {
    /* 拦截器已提示；当前密码错误时后端返回 400 */
  } finally {
    pwdLoading.value = false
  }
}

function logout() {
  portalAuth.clear()
  router.replace({ name: 'portal-login' })
}
</script>

<template>
  <div class="portal-page">
    <section class="portal-card profile-hero">
      <UserAvatar
        :fetch-blob="portalAuthApi.avatarBlob"
        :upload="portalAuthApi.updateAvatar"
        editable
        :name="candidate.name || '候选人'"
        :size="80"
        @updated="onAvatarUpdated"
      />
      <div>
        <div class="profile-name">{{ candidate.name || '候选人' }}</div>
        <div class="profile-phone">{{ candidate.phone || '未绑定手机号' }}</div>
      </div>
      <span class="status-pill" :class="user.is_active === false ? 'fail' : 'pass'">
        {{ user.is_active === false ? '已停用' : '正常' }}
      </span>
    </section>

    <section class="portal-card">
      <h2 class="portal-section-title">我的资料</h2>
      <p class="portal-small" style="margin: 0 0 10px">
        个人资料表、职业底色图请到「文件 → 我的表单」统一填写。
      </p>
      <div class="profile-list">
        <div class="profile-row">
          <span class="label">姓名</span>
          <span class="value">{{ candidate.name || '—' }}</span>
        </div>
        <div class="profile-row">
          <span class="label">手机号</span>
          <span class="value">{{ candidate.phone || '—' }}</span>
        </div>
        <div class="profile-row">
          <span class="label">邮箱</span>
          <span class="value">{{ candidate.email || '未填写（可由 HR 补充）' }}</span>
        </div>
      </div>
    </section>

    <section class="portal-card">
      <h2 class="portal-section-title">设置</h2>
      <div class="profile-row">
        <span class="label">主题</span>
        <el-radio-group :model-value="theme" size="small" @update:model-value="applyTheme">
          <el-radio-button v-for="t in THEMES" :key="t.value" :value="t.value">{{ t.label }}</el-radio-button>
        </el-radio-group>
      </div>
      <div class="profile-row">
        <span class="label">密码</span>
        <el-button size="small" @click="openPassword">修改密码</el-button>
      </div>
      <div class="profile-row">
        <span class="label">登录</span>
        <el-button size="small" type="danger" plain @click="logout">退出登录</el-button>
      </div>
    </section>

    <p class="portal-small" style="text-align: center">
      简历与档案由 HR 维护；如需更新手机号或简历，请联系 HR。
    </p>

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
  </div>
</template>

<style scoped>
.profile-hero {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
}
.profile-hero .status-pill {
  margin-left: auto;
}
</style>
