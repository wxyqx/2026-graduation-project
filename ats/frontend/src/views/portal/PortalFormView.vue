<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import PortalFormRenderer from '../../components/PortalFormRenderer.vue'
import { portalFormApi } from '../../api/portal'

const route = useRoute()
const router = useRouter()

const template = ref(null)
const submission = ref(null)
const answers = ref({})
const loading = ref(true)
const saving = ref(false)
const submitting = ref(false)

const SCOPE_LABEL = { profile: '个人资料表', position: '岗位申请表', assessment: '职业底色图' }

const templateId = computed(() => route.params.templateId)
const applicationId = computed(() => route.query.application_id || null)
const fields = computed(() => template.value?.fields || [])
const submitted = computed(() => submission.value?.status === 'submitted')
const backTo = { name: 'portal-forms-center' }

function initAnswers() {
  const next = {}
  const current = submission.value?.answers || {}
  for (const f of fields.value) {
    const value = current[f.field_key]
    if (f.field_type === 'checkbox' || f.field_type === 'daterange') {
      next[f.field_key] = Array.isArray(value) ? [...value] : []
    } else {
      next[f.field_key] = value ?? ''
    }
  }
  answers.value = next
}

async function load() {
  loading.value = true
  try {
    const data = await portalFormApi.detail(templateId.value, applicationId.value)
    template.value = data.template
    submission.value = data.submission
    initAnswers()
  } finally {
    loading.value = false
  }
}

function validateRequired() {
  for (const f of fields.value) {
    if (!f.required) continue
    const value = answers.value[f.field_key]
    const empty = Array.isArray(value) ? value.length === 0 : !String(value ?? '').trim()
    if (empty) {
      ElMessage.warning(`请填写「${f.label}」`)
      return false
    }
  }
  return true
}

async function save(submit) {
  if (submit && !validateRequired()) return
  if (submit) submitting.value = true
  else saving.value = true
  try {
    submission.value = await portalFormApi.save(
      templateId.value,
      answers.value,
      submit,
      applicationId.value,
    )
    ElMessage.success(submit ? '已提交' : '草稿已保存')
  } catch {
    /* 服务端校验错误由拦截器提示 */
  } finally {
    saving.value = false
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="portal-page form-shell">
    <router-link :to="backTo" class="back-link">
      <el-icon><ArrowLeft /></el-icon> 返回
    </router-link>

    <div v-if="loading" class="portal-card"><el-skeleton :rows="8" animated /></div>

    <template v-else-if="template">
      <section class="portal-card">
        <h1 class="form-title">{{ template.name }}</h1>
        <p v-if="template.description" class="form-desc">{{ template.description }}</p>
        <div class="position-meta">
          <span>{{ SCOPE_LABEL[template.scope] || '表单' }}</span>
          <span v-if="submitted">已提交 · 可修改后重新提交</span>
        </div>
      </section>

      <el-alert
        v-if="submitted"
        title="这份表单已经提交"
        type="success"
        show-icon
        :closable="false"
        description="HR 已能看到你的答案；如果需要补充，修改后点「重新提交」即可。"
      />

      <section class="portal-card">
        <PortalFormRenderer v-model="answers" :fields="fields" />
      </section>

      <div class="form-actions">
        <el-button size="large" :loading="saving" @click="save(false)">保存草稿</el-button>
        <el-button type="primary" size="large" :loading="submitting" @click="save(true)">
          {{ submitted ? '重新提交' : '提交' }}
        </el-button>
      </div>
    </template>

    <div v-else class="portal-empty">
      <el-icon><Document /></el-icon>
      <p>表单不存在或已停用</p>
      <el-button @click="router.replace(backTo)">返回</el-button>
    </div>
  </div>
</template>

<style scoped>
.form-shell {
  position: relative;
  padding: 20px;
  border-radius: 20px;
  background:
    radial-gradient(circle at 12% 4%, color-mix(in srgb, var(--el-color-primary) 12%, transparent), transparent 38%),
    linear-gradient(
      135deg,
      color-mix(in srgb, var(--el-color-primary) 7%, var(--el-bg-color-page)),
      var(--el-bg-color-page) 52%,
      color-mix(in srgb, var(--el-color-primary) 5%, var(--el-bg-color-page))
    );
}
.form-shell .portal-card {
  background: color-mix(in srgb, var(--el-bg-color) 74%, transparent);
  border: 1px solid color-mix(in srgb, var(--el-bg-color) 72%, transparent);
  backdrop-filter: blur(20px) saturate(135%);
  -webkit-backdrop-filter: blur(20px) saturate(135%);
  box-shadow: 0 14px 40px rgb(10 40 36 / 8%);
}
.form-shell :deep(.form-section) {
  background: color-mix(in srgb, var(--el-fill-color-light) 68%, transparent);
  border: 1px solid color-mix(in srgb, var(--el-bg-color) 65%, transparent);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.form-shell :deep(.el-input__wrapper),
.form-shell :deep(.el-textarea__inner) {
  background: color-mix(in srgb, var(--el-bg-color) 58%, transparent);
}
.form-shell :deep(.el-input__wrapper) {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--el-border-color) 72%, transparent);
}
.form-shell :deep(.el-textarea__inner) {
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--el-border-color) 72%, transparent);
}
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-secondary);
  text-decoration: none;
  font-size: var(--ats-fs-note);
  width: fit-content;
}
.form-title {
  margin: 0;
  font-size: 20px;
  font-weight: var(--ats-fw-bold);
}
@media (max-width: 759px) {
  .form-shell {
    padding: 12px;
    border-radius: 16px;
  }
  .form-shell .form-actions {
    background: color-mix(in srgb, var(--el-bg-color) 72%, transparent);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border-top: 1px solid color-mix(in srgb, var(--el-border-color) 60%, transparent);
  }
}
</style>
