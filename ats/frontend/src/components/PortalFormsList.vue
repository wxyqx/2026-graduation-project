<!--
  【我的表单列表】候选人端共用的表单列表：通用表单 + 岗位申请表两组。
  点表单行直接进该表单的专门填写页。「文件」页与「我的表单」页共用。
-->
<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { portalApplicationApi, portalFormApi } from '../api/portal'

const router = useRouter()
const forms = ref([])
const loading = ref(true)

const FORM_STATUS = { none: '未填写', draft: '草稿', submitted: '已提交' }
const SCOPE_LABEL = { profile: '个人资料表', position: '岗位申请表', assessment: '职业底色图' }

const globalForms = computed(() => forms.value.filter((f) => f.scope !== 'position'))
const positionForms = computed(() => forms.value.filter((f) => f.scope === 'position'))

async function load() {
  loading.value = true
  try {
    const [globalList, applications] = await Promise.all([
      portalFormApi.list(),
      portalApplicationApi.list(),
    ])
    const list = [...globalList]
    for (const app of applications) {
      const appForms = await portalFormApi.list(app.id)
      for (const f of appForms) {
        if (f.scope === 'position') list.push({ ...f, application_id: app.id, position_label: app.position?.name })
      }
    }
    forms.value = list
  } finally {
    loading.value = false
  }
}

function statusType(status) {
  if (status === 'submitted') return 'success'
  if (status === 'draft') return 'warning'
  return 'info'
}

function openForm(form) {
  const query = form.scope === 'position' && form.application_id ? { application_id: form.application_id } : {}
  router.push({ name: 'portal-form', params: { templateId: form.id }, query })
}

onMounted(load)
</script>

<template>
  <div v-if="loading" class="portal-card"><el-skeleton :rows="4" animated /></div>

  <template v-else>
    <section class="portal-card">
      <h2 class="portal-section-title">通用表单</h2>
      <div v-if="!globalForms.length" class="portal-empty-inline">HR 还没配置表单</div>
      <div v-for="form in globalForms" :key="form.id" class="form-row" @click="openForm(form)">
        <div class="form-main">
          <div class="form-name">{{ form.name }}</div>
          <span class="portal-small">{{ SCOPE_LABEL[form.scope] }}</span>
        </div>
        <div class="form-side">
          <el-tag size="small" effect="plain" :type="statusType(form.my_status)">
            {{ FORM_STATUS[form.my_status] || form.my_status }}
          </el-tag>
          <el-icon class="form-caret"><ArrowRight /></el-icon>
        </div>
      </div>
    </section>

    <section class="portal-card">
      <h2 class="portal-section-title">岗位申请表</h2>
      <div v-if="!positionForms.length" class="portal-empty-inline">还没有投递记录；投递后对应的岗位表会出现在这里</div>
      <div v-for="form in positionForms" :key="`${form.id}:${form.application_id}`" class="form-row" @click="openForm(form)">
        <div class="form-main">
          <div class="form-name">{{ form.name }}</div>
          <span class="portal-small">{{ form.position_label || '岗位申请表' }} · 投递 #{{ form.application_id }}</span>
        </div>
        <div class="form-side">
          <el-tag size="small" effect="plain" :type="statusType(form.my_status)">
            {{ FORM_STATUS[form.my_status] || form.my_status }}
          </el-tag>
          <el-icon class="form-caret"><ArrowRight /></el-icon>
        </div>
      </div>
    </section>

    <p class="portal-small forms-tip">表单提交后可随时回来修改重新提交。</p>
  </template>
</template>

<style scoped>
.form-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ats-sp-3);
  padding: var(--ats-sp-3) 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  cursor: pointer;
}
.form-row:last-child {
  border-bottom: 0;
}
.form-main {
  min-width: 0;
}
.form-name {
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.form-side {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
  flex: none;
}
.form-caret {
  color: var(--el-text-color-placeholder);
}
.portal-empty-inline {
  padding: var(--ats-sp-3) 0;
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-placeholder);
}
.forms-tip {
  text-align: center;
  margin: var(--ats-sp-2) 0 0;
}
</style>
