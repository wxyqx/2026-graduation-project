<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { portalPositionApi } from '../../api/portal'

const router = useRouter()
const positions = ref([])
const loading = ref(true)

async function load() {
  loading.value = true
  try {
    positions.value = await portalPositionApi.list()
  } finally {
    loading.value = false
  }
}

function open(position) {
  router.push({ name: 'portal-position-detail', params: { id: position.id } })
}

onMounted(load)
</script>

<template>
  <div class="portal-page">
    <div class="portal-page-head">
      <div>
        <h1>在招岗位</h1>
        <div class="portal-page-sub">选择一个岗位，查看详情并投递</div>
      </div>
      <span v-if="!loading" class="portal-small">{{ positions.length }} 个</span>
    </div>

    <template v-if="loading">
      <div v-for="i in 3" :key="i" class="portal-card">
        <el-skeleton :rows="3" animated />
      </div>
    </template>

    <div v-else-if="!positions.length" class="portal-empty">
      <el-icon><Briefcase /></el-icon>
      <p>暂时没有在招岗位</p>
      <span class="portal-small">HR 发布岗位后会显示在这里</span>
    </div>

    <div v-else class="position-grid">
      <article
        v-for="p in positions"
        :key="p.id"
        class="portal-card position-card"
        tabindex="0"
        role="button"
        :aria-label="`查看岗位 ${p.name}`"
        @click="open(p)"
        @keyup.enter="open(p)"
      >
        <div class="position-card-top">
          <div>
            <h2 class="position-title">{{ p.name || '未命名岗位' }}</h2>
            <div class="position-meta">
              <span v-if="p.owner">负责人：{{ p.owner }}</span>
              <span v-if="p.has_position_form">需填岗位申请表</span>
            </div>
          </div>
          <el-tag v-if="p.applied" type="success" effect="light" size="small">已投递</el-tag>
        </div>
        <p class="position-req">{{ p.requirements_summary || '暂无岗位要求' }}</p>
        <div class="position-card-foot">
          <span class="portal-small">查看详情</span>
          <el-icon><ArrowRight /></el-icon>
        </div>
      </article>
    </div>
  </div>
</template>

<style scoped>
.position-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--ats-sp-2);
}
.position-card-foot {
  margin-top: var(--ats-sp-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: var(--el-text-color-placeholder);
  font-size: var(--ats-fs-label);
}
.position-card:hover .position-card-foot {
  color: var(--el-color-primary);
}
</style>
