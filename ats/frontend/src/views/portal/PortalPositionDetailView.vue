<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { portalApplicationApi, portalPositionApi } from '../../api/portal'

const route = useRoute()
const router = useRouter()

const position = ref(null)
const loading = ref(true)
const applying = ref(false)

const canApply = computed(() => position.value && !position.value.applied)
const needProfile = computed(
  () => position.value?.profile_form_required && !position.value?.profile_form_submitted,
)

async function load() {
  loading.value = true
  try {
    position.value = await portalPositionApi.detail(route.params.id)
  } finally {
    loading.value = false
  }
}

async function apply() {
  if (!position.value || position.value.applied) return
  if (needProfile.value) {
    ElMessage.warning('请先填写并提交个人资料表')
    router.push({ name: 'portal-profile' })
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认投递「${position.value.name}」？将使用 HR 上传的当前简历。`,
      '确认投递',
      { confirmButtonText: '确认投递', cancelButtonText: '再想想', type: 'info' },
    )
  } catch {
    return
  }
  applying.value = true
  try {
    const res = await portalApplicationApi.apply(position.value.id)
    ElMessage.success(res.message || '投递成功')
    router.replace({ name: 'portal-application-detail', params: { id: res.application.id } })
  } catch {
    /* 错误提示由拦截器统一弹出（例如 HR 还没上传简历） */
  } finally {
    applying.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="portal-page">
    <router-link :to="{ name: 'portal-positions' }" class="back-link">
      <el-icon><ArrowLeft /></el-icon> 返回岗位列表
    </router-link>

    <template v-if="loading">
      <div class="portal-card"><el-skeleton :rows="6" animated /></div>
    </template>

    <template v-else-if="position">
      <section class="portal-card">
        <div class="detail-head">
          <div>
            <h1 class="detail-title">{{ position.name }}</h1>
            <div class="position-meta">
              <span v-if="position.owner">负责人：{{ position.owner }}</span>
              <span v-if="position.has_position_form">投递后需填写岗位申请表</span>
            </div>
          </div>
          <el-tag v-if="position.applied" type="success" effect="light">已投递</el-tag>
        </div>
      </section>

      <section class="portal-card">
        <h2 class="portal-section-title">岗位要求</h2>
        <p class="jd-text">{{ position.requirements || 'HR 暂未填写岗位要求' }}</p>
      </section>

      <el-alert
        v-if="needProfile"
        title="投递前需要先完善个人资料表"
        type="warning"
        show-icon
        :closable="false"
      >
        <template #default>
          <div class="alert-body">
            <span>HR 配置了个人资料表，提交后才能投递。</span>
            <el-button size="small" type="primary" plain @click="router.push({ name: 'portal-files' })">
              去填写
            </el-button>
          </div>
        </template>
      </el-alert>

      <div class="detail-actions">
        <el-button v-if="position.applied" type="success" plain disabled>已投递</el-button>
        <el-button v-else type="primary" size="large" :loading="applying" @click="apply">
          {{ needProfile ? '先完善个人资料表' : '立即投递' }}
        </el-button>
        <el-button v-if="position.applied" size="large" @click="router.push({ name: 'portal-applications' })">
          查看我的投递
        </el-button>
      </div>
    </template>

    <div v-else class="portal-empty">
      <el-icon><Briefcase /></el-icon>
      <p>岗位不存在或已停止招聘</p>
      <el-button @click="router.replace({ name: 'portal-positions' })">回到岗位列表</el-button>
    </div>
  </div>
</template>

<style scoped>
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--el-text-color-secondary);
  text-decoration: none;
  font-size: var(--ats-fs-note);
  width: fit-content;
}
.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ats-sp-3);
}
.detail-title {
  margin: 0;
  font-size: 22px;
  font-weight: var(--ats-fw-bold);
  letter-spacing: -0.01em;
}
.jd-text {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}
.alert-body {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ats-sp-3);
  flex-wrap: wrap;
  margin-top: 4px;
}
.detail-actions {
  display: flex;
  gap: var(--ats-sp-2);
  flex-wrap: wrap;
}
.detail-actions .el-button {
  flex: 1;
  min-width: 140px;
}
</style>
