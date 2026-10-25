<!--
  【7 关进度条】候选人端用，比管理端的密集表格更适合手机。

  两种用法：
    <PortalStageBar :current-stage="app.current_stage" :status="app.overall_status" />
    <PortalStageBar :timeline="app.timeline" />
  颜色沿用主题里的 --ats-stage-* 色阶：越往后越深。
-->
<script setup>
import { computed } from 'vue'

import { STAGE_COLOR, STAGE_INDEX, STAGES } from '../constants'

const props = defineProps({
  currentStage: { type: String, default: '' },
  status: { type: String, default: 'pending' },
  timeline: { type: Array, default: null },
})

const steps = computed(() => {
  if (Array.isArray(props.timeline) && props.timeline.length) {
    return props.timeline.map((item, i) => ({
      stage: item.stage,
      label: item.label,
      state: item.state,
      time: item.time,
      color: STAGE_COLOR[item.stage] || 'var(--el-color-info)',
      index: i,
    }))
  }
  const current = STAGE_INDEX[props.currentStage] ?? 0
  return STAGES.map((s, i) => {
    let state = 'waiting'
    if (i < current) state = 'passed'
    else if (i === current) {
      if (props.status === 'fail') state = 'failed'
      else if (props.status === 'pass') state = 'passed'
      else state = 'current'
    }
    return {
      stage: s.value,
      label: s.label,
      state,
      time: null,
      color: STAGE_COLOR[s.value],
      index: i,
    }
  })
})
</script>

<template>
  <ol class="stage-bar" :aria-label="`招聘进度：${steps.find((s) => s.state === 'current')?.label || ''}`">
    <li
      v-for="step in steps"
      :key="step.stage"
      class="stage-step"
      :class="step.state"
      :title="step.time ? `${step.label}：${step.time}` : step.label"
    >
      <span class="stage-dot" :style="step.state === 'waiting' ? {} : { background: step.color }" />
      <span class="stage-label">{{ step.label }}</span>
    </li>
  </ol>
</template>

<style scoped>
.stage-bar {
  list-style: none;
  display: grid;
  grid-template-columns: repeat(7, minmax(0, 1fr));
  gap: 0;
  margin: 0;
  padding: 0;
  position: relative;
}
/* 贯穿的底线：未走到的部分 */
.stage-bar::before {
  content: '';
  position: absolute;
  left: 7%;
  right: 7%;
  top: 6px;
  height: 2px;
  background: var(--ats-track);
  border-radius: 1px;
}
.stage-step {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
}
.stage-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--ats-track);
  border: 2px solid var(--el-bg-color);
  box-sizing: border-box;
}
.stage-step.current .stage-dot {
  width: 14px;
  height: 14px;
  margin-top: -1px;
  box-shadow: 0 0 0 3px var(--el-color-primary-light-8);
}
.stage-step.failed .stage-dot {
  background: var(--el-color-danger) !important;
}
.stage-label {
  font-size: 10px;
  line-height: 1.2;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
  transform: scale(0.92);
}
.stage-step.passed .stage-label,
.stage-step.current .stage-label {
  color: var(--el-text-color-regular);
  font-weight: var(--ats-fw-medium);
}
.stage-step.failed .stage-label {
  color: var(--el-color-danger);
}
</style>
