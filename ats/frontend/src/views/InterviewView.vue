<!--
  【面试评价页】
  面试完把对话逐字稿整段贴进来 → 点「生成面试评价」→ AI 按固定的 7 项模板写出一份面评，
  显示在下方，点「复制」拿走即可。

  评价不存数据库、不进浏览器存储，刷新页面就没了 —— 这里只是个「贴稿 → 出评 → 复制」的过路站。

  右上角的 AI 配置、启用与否在「系统设置」页里管；没启用任何配置时后端会回 400，本页给个提示条。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, ref } from 'vue'

import { interviewApi } from '../api'

const transcript = ref('')
const result = ref('')
const configUsed = ref('')
const running = ref(false)

// 逐字稿字数（按字符算，跟后端 3 万字上限对齐）
const charCount = computed(() => transcript.value.length)
const tooLong = computed(() => charCount.value > 30000)
// 少于 30 字后端会拦，这里也先禁用按钮，省一次白跑
const canSubmit = computed(() => transcript.value.trim().length >= 30 && !tooLong.value && !running.value)

async function generate() {
  running.value = true
  result.value = ''
  configUsed.value = ''
  try {
    const data = await interviewApi.evaluate(transcript.value)
    result.value = data.text
    configUsed.value = data.config_used
    ElMessage.success('面试评价已生成')
  } catch {
    /* 拦截器已经弹了中文提示（逐字稿太短 / 没配 AI / AI 调用失败），这里不用再管 */
  } finally {
    running.value = false
  }
}

async function copyResult() {
  if (!result.value) return
  try {
    await navigator.clipboard.writeText(result.value)
    ElMessage.success('已复制到剪贴板')
  } catch {
    // 浏览器不给剪贴板权限（非 https / 旧浏览器）时的兜底：选中 + 执行复制
    const box = document.getElementById('interview-result')
    if (box) {
      const range = document.createRange()
      range.selectNodeContents(box)
      const sel = window.getSelection()
      sel.removeAllRanges()
      sel.addRange(range)
      const ok = document.execCommand('copy')
      sel.removeAllRanges()
      ElMessage[ok ? 'success' : 'warning'](ok ? '已复制到剪贴板' : '复制失败，请手动选中后按 Ctrl+C')
    }
  }
}

function clearAll() {
  transcript.value = ''
  result.value = ''
  configUsed.value = ''
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>面试评价</h2>
    </div>

    <!-- 输入区 -->
    <section class="ats-panel">
      <h3 class="ats-panel-title">
        <span>面试逐字稿</span>
        <span class="muted" style="font-weight: normal; font-size: 12px">
          带不带时间戳、说话人怎么标都可以，系统自己分得清面试官和候选人
        </span>
      </h3>
      <el-input
        v-model="transcript"
        type="textarea"
        aria-label="面试逐字稿"
        :rows="14"
        resize="vertical"
        placeholder="把面试的对话逐字稿整段粘贴到这里……&#10;例：&#10;面试官 10:30:13&#10;你现在厦门吗？&#10;候选人 10:30:24&#10;对，在厦门。"
      />
      <div class="actions">
        <span class="muted" :class="{ 'over-limit': tooLong }">
          {{ charCount }} 字<template v-if="tooLong">（超出 3 万字上限，请分段提交）</template>
        </span>
        <div>
          <el-button :disabled="!transcript" @click="clearAll">清空</el-button>
          <el-button type="primary" :loading="running" :disabled="!canSubmit" @click="generate">
            {{ running ? 'AI 生成中…' : '生成面试评价' }}
          </el-button>
        </div>
      </div>
      <p v-if="running" class="muted hint">AI 正在阅读逐字稿并撰写评价，通常需要十几秒到一分钟，请稍候。</p>
    </section>

    <!-- 结果区 -->
    <section v-if="result" class="ats-panel">
      <h3 class="ats-panel-title">
        <span>面试评价</span>
        <span class="result-actions">
          <span v-if="configUsed" class="muted" style="font-size: 12px">由「{{ configUsed }}」生成</span>
          <el-button type="primary" size="small" @click="copyResult">复制</el-button>
        </span>
      </h3>
      <pre id="interview-result" class="result">{{ result }}</pre>
    </section>
  </div>
</template>

<style scoped>
.actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
}
.over-limit {
  color: var(--el-color-danger);
}
.hint {
  margin: 10px 0 0;
}
.result-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
/* 评价正文：保留换行与缩进，等宽字体方便对齐题面 */
.result {
  margin: 0;
  padding: 14px 16px;
  background: var(--el-fill-color-light);
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.9;
  color: var(--el-text-color-primary);
  max-height: 60vh;
  overflow: auto;
}
</style>
