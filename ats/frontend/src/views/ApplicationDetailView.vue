<!--
  【投递详情页】一条投递的全貌。

  设计说明（v3.12）：这一页的主体是「7 关管线」，不再是几张并列的信息卡。
    · 候选人 / 岗位信息压缩成顶部一条信息带，把版面让给管线
    · 管线是页面主角：每关一个节点，连接线按进度染色；已过的关实心带对勾，
      当前关加光晕并标「进行中」，被淘汰的关整节点标红
    · 结果与时间拆成两个元素显示，不再用「通过 · 2026-09-15 13:34」这种中点拼接
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed, inject, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { applicationApi, candidateApi } from '../api'
import { RESULT_LABEL, STAGE_COLOR, STAGE_LABEL, STATUS_LABEL, STATUS_TYPE, stageHasEvaluation } from '../constants'
import { fmtTime } from '../utils/format'
import StageNoteDialog from './StageNoteDialog.vue'

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

// 返回列表：能用浏览器后退就用后退（带着原来的筛选条件回去）；
// 直接打开这个网址（没有上一页）就退回投递列表首页
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push({ name: 'applications' })
}

const activeIndex = computed(() => {
  if (!app.value) return 0
  return app.value.stages.findIndex((s) => s.stage === app.value.current_stage)
})

// 每一关在管线上的形态
function nodeState(s, i) {
  if (s.result === 'fail') return 'rejected'
  if (s.result === 'pass') return 'passed'
  if (i === activeIndex.value) return app.value?.overall_status === 'pass' ? 'passed' : 'current'
  return 'upcoming'
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

// ---- 改候选人姓名（AI 有时会认错名字，人工纠正）----
async function renameCandidate() {
  const cur = app.value?.candidate
  if (!cur) return
  let input
  try {
    const res = await ElMessageBox.prompt('请输入正确的姓名', '修改候选人姓名', {
      inputValue: cur.name || '',
      inputPlaceholder: '例：樊浩',
      inputValidator: (v) => (v && v.trim() ? true : '姓名不能为空'),
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    input = res.value.trim()
  } catch {
    return // 取消
  }
  if (input === (cur.name || '').trim()) return // 没改动

  try {
    await candidateApi.update(cur.id, { name: input })
  } catch (e) {
    // 409 = 与已有候选人重名：把后端的中文说明给用户看，确认后再带 confirm_duplicate 提交
    if (e.response?.status === 409) {
      try {
        await ElMessageBox.confirm(e.detail || '已有同名候选人，确定要继续吗？', '重名提示', {
          type: 'warning',
          confirmButtonText: '仍要改成同名',
          cancelButtonText: '取消',
        })
      } catch {
        return
      }
      await candidateApi.update(cur.id, { name: input, confirm_duplicate: true })
    } else {
      throw e
    }
  }
  ElMessage.success('姓名已更新')
  await load()
  refreshStats?.()
}

// ---- 各关记录（可编辑的结果原因 / 面试评价）----
// 列出「已出结果的人工关」+「正在进行中的当前关」——进行中也能先写（面试完就记评价，之后再定通过/淘汰）。
// ai 关不在此列，它有独立面板，理由由 AI 生成、不可手改。
const noteStages = computed(() =>
  (app.value?.stages || []).filter((s) => s.stage !== 'ai' && (s.result || s.is_current)),
)

const noteDialog = ref({ visible: false, stage: '', result: '', reason: '', evaluation: '' })
function openNote(s) {
  noteDialog.value = {
    visible: true,
    stage: s.stage,
    result: s.result,
    reason: s.reason || '',
    evaluation: s.evaluation || '',
  }
}
async function onNoteSaved() {
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
        <h2 v-if="app">{{ app.candidate?.name }}</h2>
        <el-tag v-if="app" :type="STATUS_TYPE[app.overall_status]" size="small" effect="light">
          {{ STATUS_LABEL[app.overall_status] }}
        </el-tag>
        <span v-if="app" class="muted">{{ app.position?.position_name }}</span>
      </div>
      <div v-if="app">
        <el-button type="primary" :disabled="!isPending" @click="advance('pass')">
          通过「{{ STAGE_LABEL[app.current_stage] }}」
        </el-button>
        <el-button type="danger" plain :disabled="!isPending" @click="advance('fail')">淘汰</el-button>
        <el-button :disabled="!canRevert" @click="revert">撤回</el-button>
      </div>
    </div>

    <template v-if="app">
      <!-- 信息带：候选人 + 岗位压缩成一行，版面让给管线 -->
      <div class="meta-band">
        <div class="meta-item">
          <span class="meta-label">姓名</span>
          <span class="meta-value">
            {{ app.candidate?.name }}
            <el-button link type="primary" size="small" @click="renameCandidate">改姓名</el-button>
          </span>
        </div>
        <div class="meta-item">
          <span class="meta-label">备注</span>
          <span class="meta-value">{{ app.candidate?.remark || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">负责人</span>
          <span class="meta-value">{{ app.position?.owner || '—' }}</span>
        </div>
        <div class="meta-item">
          <span class="meta-label">录入时间</span>
          <span class="meta-value ats-nums">{{ fmtTime(app.candidate?.create_time) }}</span>
        </div>
      </div>

      <!-- 管线：本页主体 -->
      <section class="panel">
        <div class="panel-head">
          <h3>招聘流程</h3>
          <span class="muted">当前在「{{ STAGE_LABEL[app.current_stage] }}」</span>
        </div>

        <ol class="pipeline">
          <li
            v-for="(s, i) in app.stages"
            :key="s.stage"
            class="node"
            :class="`is-${nodeState(s, i)}`"
          >
            <span class="node-dot" :style="{ background: STAGE_COLOR[s.stage] }">
              <el-icon v-if="s.result === 'pass'"><Select /></el-icon>
              <el-icon v-else-if="s.result === 'fail'"><CloseBold /></el-icon>
            </span>
            <span class="node-name">{{ s.label }}</span>
            <span v-if="s.result" class="node-result" :class="s.result">{{ RESULT_LABEL[s.result] }}</span>
            <span v-else-if="s.is_current && isPending" class="node-result current">进行中</span>
            <span v-if="s.time" class="node-time ats-nums">{{ fmtTime(s.time) }}</span>
          </li>
        </ol>
      </section>

      <section class="panel">
        <h3>岗位要求</h3>
        <p class="req">{{ app.position?.position_requirements || '—' }}</p>
      </section>

      <section class="panel">
        <h3>AI 筛选</h3>
        <template v-if="app.ai_result">
          <el-tag :type="app.ai_result === 'pass' ? 'success' : 'danger'" size="small" effect="light">
            {{ RESULT_LABEL[app.ai_result] }}
          </el-tag>
          <p class="ai-comment">{{ app.ai_comment || '（AI 未给出理由）' }}</p>
        </template>
        <span v-else class="muted">尚未进行 AI 筛选。手动通过第一关即视为人工代替 AI 筛选。</span>
      </section>

      <!-- 各关记录：推进时一键不留文字，事后来这里补写原因 / 面试评价 -->
      <section class="panel">
        <div class="panel-head">
          <h3>各关记录</h3>
          <span class="muted">补写各关的通过 / 淘汰原因与面试评价</span>
        </div>

        <div v-if="noteStages.length" class="note-list">
          <div v-for="s in noteStages" :key="s.stage" class="note-item">
            <div class="note-head">
              <span class="note-dot" :style="{ background: STAGE_COLOR[s.stage] }" />
              <span class="note-stage">{{ s.label }}</span>
              <el-tag v-if="s.result" size="small" effect="light" :type="s.result === 'pass' ? 'success' : 'danger'">
                {{ RESULT_LABEL[s.result] }}
              </el-tag>
              <span v-else class="note-current">进行中</span>
              <span v-if="s.time" class="muted ats-nums">{{ fmtTime(s.time) }}</span>
              <el-button class="note-edit" link type="primary" size="small" @click="openNote(s)">编辑</el-button>
            </div>

            <div class="note-field">
              <span class="note-label">原因</span>
              <span v-if="s.reason" class="note-text">{{ s.reason }}</span>
              <span v-else class="muted">尚未填写</span>
            </div>

            <div v-if="stageHasEvaluation(s.stage)" class="note-field">
              <span class="note-label">面试评价</span>
              <pre v-if="s.evaluation" class="note-eval">{{ s.evaluation }}</pre>
              <span v-else class="muted">尚未填写</span>
            </div>
          </div>
        </div>
        <p v-else class="muted note-empty">还没有可记录的阶段（AI 筛选的理由见上方）。推进到人工环节后，可在这里写原因与面试评价。</p>
      </section>
    </template>

    <!-- 各关记录的编辑弹窗 -->
    <StageNoteDialog
      v-if="app"
      v-model="noteDialog.visible"
      :app-id="app.id"
      :stage="noteDialog.stage"
      :result="noteDialog.result"
      :reason="noteDialog.reason"
      :evaluation="noteDialog.evaluation"
      @saved="onNoteSaved"
    />
  </div>
</template>

<style scoped>
.title-row {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
}

/* ---- 信息带 ---- */
.meta-band {
  display: flex;
  flex-wrap: wrap;
  gap: var(--ats-sp-6);
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-3) var(--ats-sp-4);
  margin-bottom: var(--ats-sp-4);
}
.meta-item {
  display: flex;
  align-items: baseline;
  gap: var(--ats-sp-2);
}
.meta-label {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.meta-value {
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-primary);
  overflow-wrap: anywhere;
}

/* ---- 分区面板 ---- */
.panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-4);
  margin-bottom: var(--ats-sp-4);
}
.panel h3 {
  margin: 0 0 var(--ats-sp-3);
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
}
.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--ats-sp-3);
}

/* ---- 管线 ---- */
.pipeline {
  list-style: none;
  margin: var(--ats-sp-6) 0 var(--ats-sp-2);
  padding: 0;
  display: flex;
}
.node {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
  text-align: center;
}
/* 节点之间的连接线：左右各画半条，拼成一条贯穿的轨道 */
.node::before,
.node::after {
  content: '';
  position: absolute;
  top: 13px;
  height: 2px;
  background: var(--ats-track);
}
.node::before {
  left: 0;
  right: 50%;
}
.node::after {
  left: 50%;
  right: 0;
}
.node:first-child::before,
.node:last-child::after {
  display: none;
}
/* 走过的路：连接线染成阶段色，读起来是"进度在推进" */
.node.is-passed::before,
.node.is-passed::after,
.node.is-rejected::before,
.node.is-current::before {
  background: var(--ats-stage-5);
}

.node-dot {
  position: relative;
  z-index: 1;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 13px;
}
/* 未到达：空心描边，形状保留但退到背景里 */
.node.is-upcoming .node-dot {
  background: var(--el-bg-color) !important;
  border: 2px solid var(--ats-track);
}
/* 当前：加一圈光晕，明确"停在这一关" */
.node.is-current .node-dot {
  box-shadow: 0 0 0 4px var(--el-color-primary-light-8);
}
/* 淘汰：整节点用语义色，读起来是"终止" */
.node.is-rejected .node-dot {
  background: var(--el-color-danger) !important;
  box-shadow: 0 0 0 4px var(--el-color-danger-light-9);
}

.node-name {
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-regular);
  font-weight: var(--ats-fw-medium);
}
.node.is-upcoming .node-name {
  color: var(--el-text-color-placeholder);
  font-weight: var(--ats-fw-normal);
}
.node-result {
  font-size: var(--ats-fs-label);
}
.node-result.pass {
  color: var(--el-color-success);
}
.node-result.fail {
  color: var(--el-color-danger);
}
.node-result.current {
  color: var(--el-color-primary);
}
.node-time {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
}

.req {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}
.ai-comment {
  margin: var(--ats-sp-2) 0 0;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

/* ---- 各关记录 ---- */
.note-list {
  display: flex;
  flex-direction: column;
  gap: var(--ats-sp-3);
  margin-top: var(--ats-sp-3);
}
.note-item {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-3);
}
.note-head {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
/* 与管线里同一关同色的小色条，让两处一眼对得上 */
.note-dot {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  flex: none;
}
.note-stage {
  font-size: var(--ats-fs-body);
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
.note-edit {
  margin-left: auto;
}
/* 进行中的当前关：没有通过/淘汰标签，用主色文字标出「还没定」 */
.note-current {
  font-size: var(--ats-fs-label);
  color: var(--el-color-primary);
}
.note-field {
  display: flex;
  gap: var(--ats-sp-3);
  margin-top: var(--ats-sp-2);
}
.note-label {
  flex: none;
  width: 56px;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
  line-height: 1.9;
}
.note-text,
.note-eval {
  margin: 0;
  font-family: inherit;
  font-size: var(--ats-fs-body);
  line-height: 1.9;
  color: var(--el-text-color-regular);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.note-empty {
  margin: var(--ats-sp-3) 0 0;
}
</style>
