<!--
  【富文本编辑器（轻量）】通知正文等短文本用：加粗 / 斜体 / 字号 / 链接 / 清除格式。
  基于 contenteditable + document.execCommand，不引入第三方依赖。
  v-model 是 HTML 字符串；写入前经 sanitize 清洗（去 script / on* 事件 / javascript: 链接）。
-->
<script setup>
import DOMPurify from 'dompurify'
import { onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  minHeight: { type: Number, default: 90 },
  // 可选：占位符插入按钮（通知模板用）——[{ label: '候选人姓名', value: '{候选人}' }, …]
  // 点击在光标处插入 value（纯文本），发送时后端替换成真实值
  placeholders: { type: Array, default: null },
})
const emit = defineEmits(['update:modelValue'])

const editor = ref(null)
let composing = false

// 纯文本（模板里写的多行文字）转成 HTML 显示；带标签的内容原样进
function toHtml(value) {
  const v = value || ''
  if (/<[a-z][\s\S]*>/i.test(v)) return v
  return v ? v.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\n/g, '<br>') : ''
}

// 手写正则/DOM 清洗是经典 XSS 来源，交给 DOMPurify 按白名单清洗（与后端 nh3 同一套能力面）
const PURIFY_CONFIG = {
  ALLOWED_TAGS: ['b', 'strong', 'i', 'em', 'u', 's', 'br', 'p', 'div', 'span', 'font',
                 'a', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'blockquote'],
  ALLOWED_ATTR: ['style', 'href', 'target', 'size', 'color', 'face'],
  ALLOWED_URI_REGEXP: /^(?:https?:|mailto:)/i,
}

function sanitize(html) {
  return DOMPurify.sanitize(html || '', PURIFY_CONFIG)
}

function onInput() {
  emit('update:modelValue', sanitize(editor.value.innerHTML))
}

function exec(command, value = null) {
  editor.value?.focus()
  document.execCommand(command, false, value)
  onInput()
}

function insertLink() {
  const url = window.prompt('链接地址（http(s)://…）')
  if (!url) return
  if (!/^https?:\/\//i.test(url)) {
    window.alert('链接需要以 http:// 或 https:// 开头')
    return
  }
  exec('createLink', url)
}

// 在光标处插入纯文本（占位符用）：insertText 保留光标位置，插完同步 v-model
function insertText(text) {
  editor.value?.focus()
  document.execCommand('insertText', false, text)
  onInput()
}

const FONT_SIZES = [
  { value: 2, label: '小' },
  { value: 3, label: '标准' },
  { value: 5, label: '大' },
]

onMounted(() => {
  editor.value.innerHTML = toHtml(props.modelValue)
})

watch(
  () => props.modelValue,
  (v) => {
    // 外部换值（如切到另一条草稿）时同步；正在输入时不打断光标
    if (document.activeElement !== editor.value && editor.value && editor.value.innerHTML !== toHtml(v)) {
      editor.value.innerHTML = toHtml(v)
    }
  },
)
</script>

<template>
  <div class="rte">
    <div class="rte-toolbar">
      <button type="button" class="rte-btn" title="加粗" @click.prevent="exec('bold')"><b>B</b></button>
      <button type="button" class="rte-btn" title="斜体" @click.prevent="exec('italic')"><i>I</i></button>
      <span class="rte-sep" />
      <button
        v-for="f in FONT_SIZES"
        :key="f.value"
        type="button"
        class="rte-btn rte-size"
        :style="{ fontSize: `${9 + f.value}px` }"
        :title="`字号：${f.label}`"
        @click.prevent="exec('fontSize', String(f.value))"
      >
        {{ f.label }}
      </button>
      <span class="rte-sep" />
      <button type="button" class="rte-btn" title="左对齐" @click.prevent="exec('justifyLeft')">⇤</button>
      <button type="button" class="rte-btn" title="居中" @click.prevent="exec('justifyCenter')">↔</button>
      <button type="button" class="rte-btn" title="右对齐" @click.prevent="exec('justifyRight')">⇥</button>
      <span class="rte-sep" />
      <button type="button" class="rte-btn" title="插入链接" @click.prevent="insertLink">链接</button>
      <button type="button" class="rte-btn" title="清除格式" @click.prevent="exec('removeFormat')">清除</button>
      <template v-if="placeholders?.length">
        <span class="rte-sep" />
        <button
          v-for="p in placeholders"
          :key="p.value"
          type="button"
          class="rte-btn rte-ph"
          :title="`插入占位符：发送时自动替换（${p.hint || p.label}）`"
          @click.prevent="insertText(p.value)"
        >
          {{ p.label }}
        </button>
      </template>
    </div>
    <div
      ref="editor"
      class="rte-editor"
      contenteditable="true"
      :style="{ minHeight: `${minHeight}px` }"
      :data-placeholder="placeholder"
      @input="onInput"
      @compositionstart="composing = true"
      @compositionend="composing = false; onInput()"
    />
  </div>
</template>

<style scoped>
.rte {
  border: 1px solid var(--el-border-color);
  border-radius: var(--ats-radius-sm, 4px);
  background: var(--el-bg-color);
}
.rte:focus-within {
  border-color: var(--el-color-primary);
}
.rte-toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 4px 6px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  flex-wrap: wrap;
}
.rte-btn {
  border: 0;
  background: transparent;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  color: var(--el-text-color-regular);
  font: inherit;
  line-height: 1.4;
}
.rte-btn:hover {
  background: var(--el-fill-color);
  color: var(--el-color-primary);
}
.rte-size {
  font-weight: var(--ats-fw-medium);
}
/* 占位符按钮：与普通工具按钮区分，提示这是会被替换的特殊标记 */
.rte-ph {
  color: var(--el-color-primary);
  border: 1px dashed var(--el-color-primary-light-5);
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
}
.rte-ph:hover {
  background: var(--el-color-primary-light-9);
}
.rte-sep {
  width: 1px;
  height: 16px;
  background: var(--el-border-color-lighter);
  margin: 0 4px;
}
.rte-editor {
  padding: 8px 12px;
  font-size: var(--ats-fs-body);
  line-height: 1.8;
  color: var(--el-text-color-regular);
  overflow-wrap: anywhere;
  outline: none;
  word-break: break-word;
}
.rte-editor:empty::before {
  content: attr(data-placeholder);
  color: var(--el-text-color-placeholder);
}
.rte-editor :deep(a) {
  color: var(--el-color-primary);
}
</style>
