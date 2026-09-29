<!--
  【阶段记录弹窗】给某一关补写「结果原因」/「面试评价」。

  为什么是弹窗：推进（通过/淘汰）仍是一键、不打断批量处理；文字记录事后在这里补，
  改哪一关就弹哪一关，不占详情页版面。

  三块内容：
    1. 抬头：这一关叫什么 + 已定结果（通过 / 淘汰，只读）
    2. 结果原因：通过或淘汰都能写（4 行文本）
    3. 面试评价：只有四个面试环节有；旁边「AI 生成」可贴逐字稿，用现有面试评价功能自动写一版，再手动润色

  保存走 applicationApi.saveStageNote，成功后 emit('saved') 让详情页重新拉数据。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, ref, watch } from 'vue'

import { applicationApi, interviewApi } from '../api'
import { RESULT_LABEL, STAGE_INDEX, STAGE_LABEL, stageHasEvaluation } from '../constants'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  appId: { type: [Number, String], required: true },
  stage: { type: String, default: '' },
  result: { type: String, default: '' },
  reason: { type: String, default: '' },
  evaluation: { type: String, default: '' },
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const stageLabel = computed(() => STAGE_LABEL[props.stage] || props.stage)
const hasEvaluation = computed(() => stageHasEvaluation(props.stage))
// 提示语跟着结果走：通过就写通过原因，淘汰就写淘汰原因
const reasonPlaceholder = computed(() =>
  props.result === 'fail'
    ? '写清楚这一关为什么淘汰，例如：学历不符 / 笔试分数偏低 / 团队匹配度不足……'
    : '写清楚这一关为什么通过，例如：本科+3年相关经验，符合岗位要求……',
)
// 色标：让弹窗抬头与详情页管线里的同一个阶段看起来是「同一关」
const stageColor = computed(() => `var(--ats-stage-${(STAGE_INDEX[props.stage] ?? 0) + 1})`)

const form = ref({ reason: '', evaluation: '' })
const saving = ref(false)

function reset() {
  form.value.reason = props.reason || ''
  form.value.evaluation = props.evaluation || ''
  aiOpen.value = false
  transcript.value = ''
}
watch(visible, (v) => v && reset(), { immediate: true })

async function save() {
  saving.value = true
  try {
    await applicationApi.saveStageNote(props.appId, props.stage, form.value.reason, form.value.evaluation)
    ElMessage.success('记录已保存')
    visible.value = false
    emit('saved')
  } finally {
    saving.value = false
  }
}

// ---- 面试评价：AI 生成（贴逐字稿 → 复用现有面试评价功能）----
const aiOpen = ref(false)
const transcript = ref('')
const aiRunning = ref(false)
const configUsed = ref('')
const transcriptLen = computed(() => transcript.value.length)
const canGenerate = computed(() => transcript.value.trim().length >= 30 && transcript.value.length <= 30000 && !aiRunning.value)

async function generateEvaluation() {
  aiRunning.value = true
  configUsed.value = ''
  try {
    const data = await interviewApi.evaluate(transcript.value)
    form.value.evaluation = data.text // 直接填进评价框，还可手动润色
    configUsed.value = data.config_used
    ElMessage.success('已生成，可自行修改后再保存')
  } catch {
    /* 拦截器已弹中文提示（逐字稿太短 / 没配 AI / 调用失败），这里不用再管 */
  } finally {
    aiRunning.value = false
  }
}
</script>

<template>
  <el-dialog
    v-model="visible"
    class="ats-dialog-wide"
    :title="`填写「${stageLabel}」记录`"
    destroy-on-close
    :close-on-click-modal="false"
  >
    <!-- 抬头：这一关 + 已定结果 -->
    <div class="head">
      <span class="dot" :style="{ background: stageColor }" />
      <span class="head-stage">{{ stageLabel }}</span>
      <el-tag v-if="result" size="small" effect="light" :type="result === 'pass' ? 'success' : 'danger'">
        {{ RESULT_LABEL[result] }}
      </el-tag>
      <span class="muted">记录只作留痕，不会改变流程状态</span>
    </div>

    <div class="field">
      <label class="field-label" for="stage-note-reason">结果原因</label>
      <el-input
        id="stage-note-reason"
        v-model="form.reason"
        type="textarea"
        :rows="4"
        maxlength="2000"
        show-word-limit
        :placeholder="reasonPlaceholder"
      />
    </div>

    <template v-if="hasEvaluation">
      <div class="field">
        <div class="field-head">
          <label class="field-label" for="stage-note-eval">面试评价</label>
          <el-button link type="primary" size="small" @click="aiOpen = !aiOpen">
            {{ aiOpen ? '收起 AI 生成' : 'AI 生成' }}
          </el-button>
        </div>

        <!-- AI 生成：贴面试逐字稿，复用「面试评价」功能按固定模板写一版 -->
        <el-collapse-transition>
          <div v-if="aiOpen" class="ai-box">
            <div class="muted ai-tip">
              把这一轮的面试逐字稿整段贴进来，点「生成」按固定模板写一版评价，填进下面的评价框后可再修改。
              需在「系统设置」里启用至少一个 AI 接口。
            </div>
            <el-input
              v-model="transcript"
              type="textarea"
              aria-label="面试逐字稿"
              :rows="6"
              placeholder="面试官 10:30:13&#10;你现在厦门吗？&#10;候选人 10:30:24&#10;对，在厦门。"
            />
            <div class="ai-actions">
              <span class="muted" :class="{ over: transcriptLen > 30000 }">{{ transcriptLen }} 字（上限 3 万）</span>
              <span class="ai-actions-right">
                <span v-if="configUsed" class="muted">由「{{ configUsed }}」生成</span>
                <el-button size="small" type="primary" :loading="aiRunning" :disabled="!canGenerate" @click="generateEvaluation">
                  {{ aiRunning ? 'AI 生成中…' : '生成并填入' }}
                </el-button>
              </span>
            </div>
          </div>
        </el-collapse-transition>

        <el-input
          id="stage-note-eval"
          v-model="form.evaluation"
          type="textarea"
          :rows="10"
          maxlength="10000"
          show-word-limit
          placeholder="面试评价：可手写，也可用上面的「AI 生成」起草后修改。"
        />
      </div>
    </template>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
  padding-bottom: var(--ats-sp-3);
  margin-bottom: var(--ats-sp-4);
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.dot {
  width: 3px;
  height: 16px;
  border-radius: 2px;
  flex: none;
}
.head-stage {
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
.head .muted {
  margin-left: auto;
  font-size: var(--ats-fs-label);
}

.field + .field {
  margin-top: var(--ats-sp-4);
}
.field-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ats-sp-2);
  margin-bottom: var(--ats-sp-2);
}
.field-label {
  display: block;
  font-size: var(--ats-fs-body);
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-regular);
  margin-bottom: var(--ats-sp-2);
}
.field-head .field-label {
  margin-bottom: 0;
}

/* AI 生成区：浅底分区，和手写的评价框在视觉上分开 */
.ai-box {
  margin-bottom: var(--ats-sp-3);
  padding: var(--ats-sp-3);
  border-radius: var(--ats-radius);
  background: var(--el-fill-color-lighter);
}
.ai-tip {
  margin-bottom: var(--ats-sp-2);
  line-height: 1.7;
}
.ai-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: var(--ats-sp-2);
}
.ai-actions-right {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
}
.over {
  color: var(--el-color-danger);
}
</style>
