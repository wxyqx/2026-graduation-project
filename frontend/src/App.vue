<script setup>
import { ref } from 'vue'
import axios from 'axios'

const health = ref(null)
const loading = ref(false)

async function checkHealth() {
  loading.value = true
  try {
    health.value = (await axios.get('/api/health')).data
  } catch {
    health.value = { status: 'error', database: 'unreachable' }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div style="max-width: 640px; margin: 80px auto; text-align: center">
    <h1>ATS 招聘管理系统</h1>
    <p style="color: #909399">M1 项目骨架已就绪</p>
    <el-button type="primary" :loading="loading" @click="checkHealth">检测后端与数据库</el-button>
    <el-result
      v-if="health"
      :icon="health.status === 'ok' ? 'success' : 'error'"
      :title="health.status === 'ok' ? '后端正常，数据库已连接' : '连接失败'"
      :sub-title="JSON.stringify(health)"
    />
  </div>
</template>
