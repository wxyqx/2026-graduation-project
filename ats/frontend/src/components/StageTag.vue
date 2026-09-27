<!--
  【阶段色标】表格与列表里显示"这个人现在走到第几关"。

  为什么不用普通标签？系统里 7 个阶段原先都是同一个灰色标签，在上百行投递里
  根本扫不出"谁在笔试、谁在专业面"。这里用一条按关卡加深的色条承载这个信息 ——
  左边缘竖条的颜色深浅 = 这一关的进度，整列竖着扫过去，深浅一目了然。

  用法：<StageTag stage="test" />
-->
<script setup>
import { computed } from 'vue'

import { STAGE_COLOR, STAGE_INDEX, STAGE_LABEL, stageTextColor } from '../constants'

const props = defineProps({
  stage: { type: String, default: '' },
  // 变体：pill = 带底色的小色块（表格里用）；plain = 只有一条细色条 + 文字（更安静）
  variant: { type: String, default: 'plain' },
})

const index = computed(() => STAGE_INDEX[props.stage] ?? 0)
const color = computed(() => STAGE_COLOR[props.stage] || 'var(--el-color-info)')
const label = computed(() => STAGE_LABEL[props.stage] || props.stage || '—')
const onColor = computed(() => stageTextColor(index.value))
</script>

<template>
  <!-- pill：整块底色，深色关用白字 -->
  <span v-if="variant === 'pill'" class="stage-pill" :style="{ background: color, color: onColor }">
    {{ label }}
  </span>

  <!-- plain：左侧一条色条 + 普通文字，信息密度更高，适合密集表格 -->
  <span v-else class="stage-plain">
    <i class="stage-bar" :style="{ background: color }" />
    <span class="stage-name">{{ label }}</span>
  </span>
</template>

<style scoped>
.stage-pill {
  display: inline-block;
  padding: 1px 8px;
  border-radius: var(--ats-radius-sm);
  font-size: var(--ats-fs-label);
  line-height: 18px;
  font-weight: var(--ats-fw-medium);
  white-space: nowrap;
}

.stage-plain {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
/* 3px 宽的竖色条：颜色按关卡加深，是这一列唯一的信息来源 */
.stage-bar {
  width: 3px;
  height: 14px;
  border-radius: 2px;
  flex: none;
}
.stage-name {
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-regular);
}
</style>
