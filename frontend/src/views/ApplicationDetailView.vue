<!--
  【投递详情页】一条投递的全貌：
    上方两张卡：候选人信息、岗位信息
    中间：8 关时间线（el-steps）——每关显示结果和时间，当前关高亮，淘汰的关标红
    下方：AI 筛选理由 + 操作按钮（通过 / 淘汰 / 撤回），操作后重新拉一次详情
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { applicationApi } from '../api'
import { RESULT_LABEL, STAGE_LABEL, STATUS_LABEL, STATUS_TYPE } from '../constants'
import { fmtTime } from '../utils/format'

const route = useRoute()
const router = useRouter()
const refreshStats = inject('refreshStats')

const app = ref(null)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    app.value = await applicationApi.detail(route.params.id)
  } finally {
    loading.value = false
  }
}
onMounted(load)

// 返回列表：能用浏览器后退就用后退（这样能带着原来的筛选条件回到列表页）；
// 如果是直接打开这个详情网址（没有上一页），就退回投递列表首页
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'applications' })
}

// el-steps 的 active 是「已完成到第几步」的数字：当前关的下标
const activeIndex = computed(() => {
  if (!app.value) return 0
  return app.value.stages.findIndex((s) => s.stage === app.value.current_stage)
})

// 每一关的显示状态：淘汰 → error；通过 → success；当前关 → process；后面的 → wait
function stepStatus(stage, index) {
  if (stage.result === 'fail') return 'error'
  if (stage.result === 'pass') return 'success'
  if (index === activeIndex.value) return app.value.overall_status === 'pass' ? 'success' : 'process'
  return 'wait'
}
function stepDesc(stage) {
  const parts = []
  if (stage.result) parts.push(RESULT_LABEL[stage.result])
  if (stage.time) parts.push(fmtTime(stage.time))
  if (!parts.length && stage.is_current && app.value.overall_status === 'pending') parts.push('进行中')
  return parts.join(' · ')
}

const isPending = computed(() => app.value?.overall_status === 'pending')
const canRevert = computed(() => app.value && !(app.value.current_stage === 'ai' && isPending.value))

async function advance(result) {
  if (result === 'fail') {
    try {
      await ElMessageBox.confirm(`确定淘汰「${app.value.candidate_name}」？`, '淘汰确认', { type: 'warning' })
    } catch {
      return
    }
  }
  await applicationApi.advance(app.value.id, app.value.current_stage, result)
  ElMessage.success(result === 'pass' ? '已通过本阶段' : '已标记淘汰')
  await load()
  refreshStats?.()
}
async function revert() {
  try {
    await ElMessageBox.confirm('撤回上一步操作？', '撤回确认', { type: 'warning' })
  } catch {
    return
  }
  await applicationApi.revert(app.value.id)
  ElMessage.success('已撤回')
  await load()
  refreshStats?.()
}
</script>

<template>
  <div v-loading="loading">
    <div class="page-header">
      <div class="title-row">
        <el-button link @click="goBack">
          <el-icon><ArrowLeft /></el-icon>&nbsp;返回列表
        </el-button>
        <h2 v-if="app">投递详情 #{{ app.id }}</h2>
      </div>
      <div v-if="app">
        <el-button type="success" :disabled="!isPending" @click="advance('pass')">通过「{{ STAGE_LABEL[app.current_stage] }}」</el-button>
        <el-button type="danger" :disabled="!isPending" @click="advance('fail')">淘汰</el-button>
        <el-button type="warning" plain :disabled="!canRevert" @click="revert">撤回</el-button>
      </div>
    </div>

    <template v-if="app">
      <el-row :gutter="14" class="cards">
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>候选人</template>
            <el-descriptions :column="1" size="small">
              <el-descriptions-item label="姓名">{{ app.candidate?.name }}</el-descriptions-item>
              <el-descriptions-item label="备注">{{ app.candidate?.remark || '—' }}</el-descriptions-item>
              <el-descriptions-item label="录入时间">{{ fmtTime(app.candidate?.create_time) }}</el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="never">
            <template #header>岗位</template>
            <el-descriptions :column="1" size="small">
              <el-descriptions-item label="岗位名称">{{ app.position?.position_name }}</el-descriptions-item>
              <el-descriptions-item label="负责人">{{ app.position?.owner || '—' }}</el-descriptions-item>
              <el-descriptions-item label="岗位要求">
                <div class="req">{{ app.position?.position_requirements || '—' }}</div>
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>
      </el-row>

      <el-card shadow="never" class="cards">
        <template #header>
          <div class="steps-header">
            <span>招聘流程</span>
            <el-tag :type="STATUS_TYPE[app.overall_status]">{{ STATUS_LABEL[app.overall_status] }}</el-tag>
          </div>
        </template>
        <el-steps :active="activeIndex" align-center>
          <el-step
            v-for="(s, i) in app.stages"
            :key="s.stage"
            :title="s.label"
            :description="stepDesc(s)"
            :status="stepStatus(s, i)"
          />
        </el-steps>
      </el-card>

      <el-card shadow="never">
        <template #header>AI 筛选</template>
        <template v-if="app.ai_result">
          <el-tag :type="app.ai_result === 'pass' ? 'success' : 'danger'">{{ RESULT_LABEL[app.ai_result] }}</el-tag>
          <p class="ai-comment">{{ app.ai_comment || '（AI 未给出理由）' }}</p>
        </template>
        <span v-else class="muted">尚未进行 AI 筛选。手动通过第一关即视为人工代替 AI 筛选。</span>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.cards {
  margin-bottom: 14px;
}
.req {
  white-space: pre-wrap;
  line-height: 1.7;
}
.steps-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.ai-comment {
  margin: 10px 0 0;
  line-height: 1.8;
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
