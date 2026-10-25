<!--
  【通用表单渲染器】按后端 Form_Field.Field_Type 渲染控件。
  12 种类型：text / textarea / number / date / daterange / select / radio / checkbox / email / phone / section / color
  候选人和 HR 看到的是同一份字段定义，这里只负责“长什么样”，校验以服务端为准。
-->
<script setup>
import { reactive } from 'vue'

const props = defineProps({
  fields: { type: Array, default: () => [] },
  modelValue: { type: Object, default: () => ({}) },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

function valueOf(key) {
  return props.modelValue?.[key]
}

function setValue(key, value) {
  emit('update:modelValue', { ...(props.modelValue || {}), [key]: value })
}

function asArray(key) {
  const v = valueOf(key)
  return Array.isArray(v) ? v : []
}

const COLOR_OPTIONS = ['红色', '蓝色', '绿色']
const COLOR_STOPS = [
  [226, 109, 103],
  [111, 143, 240],
  [67, 181, 129],
]

const colorPositions = reactive({})
const colorDragging = reactive({})

function colorIndex(key) {
  return COLOR_OPTIONS.indexOf(valueOf(key))
}

function colorValue(key) {
  if (Object.prototype.hasOwnProperty.call(colorPositions, key)) return colorPositions[key]
  const index = colorIndex(key)
  return index >= 0 ? index : null
}

function colorAt(key) {
  const value = colorValue(key)
  if (value === null) return 'transparent'
  const segment = value >= 1 ? 1 : 0
  const t = value - segment
  const from = COLOR_STOPS[segment]
  const to = COLOR_STOPS[segment + 1]
  const rgb = from.map((n, i) => Math.round(n + (to[i] - n) * t))
  return `rgb(${rgb.join(',')})`
}

function thumbLeft(key) {
  const value = colorValue(key)
  return value === null ? 0 : (value / 2) * 100
}

function updateColorFromEvent(key, event) {
  const rect = event.currentTarget.getBoundingClientRect()
  const ratio = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width))
  colorPositions[key] = ratio * 2
}

function startColorDrag(key, event) {
  event.preventDefault()
  colorDragging[key] = true
  event.currentTarget.setPointerCapture?.(event.pointerId)
  updateColorFromEvent(key, event)
}

function moveColorDrag(key, event) {
  if (!colorDragging[key]) return
  updateColorFromEvent(key, event)
}

function endColorDrag(key) {
  if (!colorDragging[key]) return
  colorDragging[key] = false
  const snapped = Math.round(colorPositions[key] ?? 0)
  colorPositions[key] = snapped
  setValue(key, COLOR_OPTIONS[snapped])
}

function stepColor(key, delta) {
  const current = colorValue(key)
  const next =
    current === null ? (delta > 0 ? 0 : 2) : Math.min(2, Math.max(0, Math.round(current) + delta))
  colorPositions[key] = next
  setValue(key, COLOR_OPTIONS[next])
}
</script>

<template>
  <div class="form-renderer">
    <el-form label-position="top" @submit.prevent>
      <template v-for="field in fields" :key="field.id || field.field_key">
        <div v-if="field.field_type === 'section'" class="form-section">
          <h3>{{ field.label }}</h3>
          <p v-if="field.help_text">{{ field.help_text }}</p>
        </div>

        <el-form-item
          v-else
          :class="{ 'span-2': ['textarea', 'checkbox', 'radio'].includes(field.field_type) }"
        >
          <template #label>
          <span class="field-label">
            {{ field.label }}
            <em v-if="field.required" class="required">*</em>
          </span>
        </template>

        <el-input
          v-if="field.field_type === 'text' || field.field_type === 'email' || field.field_type === 'phone'"
          :model-value="valueOf(field.field_key)"
          :placeholder="field.placeholder || (field.field_type === 'phone' ? '11 位手机号' : '')"
          :maxlength="field.max_length || undefined"
          :disabled="disabled"
          :inputmode="field.field_type === 'phone' ? 'tel' : undefined"
          clearable
          @update:model-value="(v) => setValue(field.field_key, v)"
        />

        <el-input
          v-else-if="field.field_type === 'textarea'"
          type="textarea"
          :rows="4"
          :model-value="valueOf(field.field_key)"
          :placeholder="field.placeholder || ''"
          :maxlength="field.max_length || undefined"
          :disabled="disabled"
          show-word-limit
          @update:model-value="(v) => setValue(field.field_key, v)"
        />

        <el-input
          v-else-if="field.field_type === 'number'"
          :model-value="valueOf(field.field_key)"
          :placeholder="field.placeholder || '请输入数字'"
          inputmode="decimal"
          :disabled="disabled"
          @update:model-value="(v) => setValue(field.field_key, v)"
        />

        <el-date-picker
          v-else-if="field.field_type === 'date'"
          :model-value="valueOf(field.field_key)"
          type="date"
          value-format="YYYY-MM-DD"
          :editable="false"
          :placeholder="field.placeholder || '选择日期'"
          :disabled="disabled"
          style="width: 100%"
          @update:model-value="(v) => setValue(field.field_key, v)"
        />

        <el-date-picker
          v-else-if="field.field_type === 'daterange'"
          :model-value="asArray(field.field_key)"
          type="daterange"
          value-format="YYYY-MM-DD"
          :editable="false"
          start-placeholder="开始时间"
          end-placeholder="结束时间"
          :disabled="disabled"
          style="width: 100%"
          @update:model-value="(v) => setValue(field.field_key, v || [])"
        />

        <el-select
          v-else-if="field.field_type === 'select'"
          :model-value="valueOf(field.field_key)"
          :placeholder="field.placeholder || '请选择'"
          :disabled="disabled"
          clearable
          style="width: 100%"
          @update:model-value="(v) => setValue(field.field_key, v)"
        >
          <el-option v-for="opt in field.options || []" :key="opt" :label="opt" :value="opt" />
        </el-select>

        <el-radio-group
          v-else-if="field.field_type === 'radio'"
          :model-value="valueOf(field.field_key)"
          :disabled="disabled"
          @update:model-value="(v) => setValue(field.field_key, v)"
        >
          <el-radio v-for="opt in field.options || []" :key="opt" :value="opt">{{ opt }}</el-radio>
        </el-radio-group>

        <div
          v-else-if="field.field_type === 'color'"
          class="color-bar-field"
          :class="{ 'is-disabled': disabled }"
        >
          <div
            class="color-slider"
            role="slider"
            tabindex="0"
            :aria-label="field.label"
            :aria-valuemin="0"
            :aria-valuemax="2"
            :aria-valuenow="colorValue(field.field_key) ?? 0"
            :aria-valuetext="valueOf(field.field_key) || '未选择'"
            @pointerdown="!disabled && startColorDrag(field.field_key, $event)"
            @pointermove="!disabled && moveColorDrag(field.field_key, $event)"
            @pointerup="endColorDrag(field.field_key)"
            @pointercancel="endColorDrag(field.field_key)"
            @keydown.left.prevent="!disabled && stepColor(field.field_key, -1)"
            @keydown.right.prevent="!disabled && stepColor(field.field_key, 1)"
          >
            <div class="color-fill" :style="{ background: colorAt(field.field_key) }" />
            <span
              v-if="colorValue(field.field_key) !== null"
              class="color-thumb"
              :style="{ left: `${thumbLeft(field.field_key)}%`, borderColor: colorAt(field.field_key) }"
            />
          </div>
        </div>

        <el-checkbox-group
          v-else-if="field.field_type === 'checkbox'"
          :model-value="asArray(field.field_key)"
          :disabled="disabled"
          @update:model-value="(v) => setValue(field.field_key, v)"
        >
          <el-checkbox v-for="opt in field.options || []" :key="opt" :value="opt">{{ opt }}</el-checkbox>
        </el-checkbox-group>

        <el-input
          v-else
          :model-value="valueOf(field.field_key)"
          :placeholder="field.placeholder || ''"
          :disabled="disabled"
          @update:model-value="(v) => setValue(field.field_key, v)"
        />

        <div v-if="field.help_text" class="field-help">{{ field.help_text }}</div>
        </el-form-item>
      </template>
    </el-form>
  </div>
</template>

<style scoped>
.form-renderer :deep(.el-form) {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 24px;
  row-gap: 14px;
}
.form-renderer :deep(.el-form-item) {
  margin-bottom: 0;
  min-width: 0;
}
.form-renderer :deep(.el-form-item__label) {
  padding-bottom: 4px;
  line-height: 1.4;
}
.form-renderer :deep(.span-2) {
  grid-column: 1 / -1;
}
.form-section {
  grid-column: 1 / -1;
  margin: 10px 0 0;
  padding: 9px 14px;
  background: var(--el-fill-color-light);
  border-left: 0;
  border-radius: 4px;
}
.form-section:first-child {
  margin-top: 0;
}
.form-section h3 {
  margin: 0;
  font-size: 14px;
  font-weight: var(--ats-fw-medium);
  color: var(--el-text-color-primary);
}
.form-section p {
  margin: 4px 0 0;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
.color-bar-field {
  width: 100%;
}
.color-bar-field.is-disabled .color-slider {
  cursor: default;
}
.color-slider {
  position: relative;
  height: 28px;
  border-radius: 999px;
  cursor: pointer;
  background: var(--el-fill-color);
  box-shadow:
    inset 0 2px 5px rgb(0 0 0 / 10%),
    inset 0 -1px 0 rgb(255 255 255 / 18%);
  outline: none;
  touch-action: none;
  user-select: none;
}
.color-slider:focus-visible {
  box-shadow:
    0 0 0 2px var(--el-bg-color),
    0 0 0 4px var(--el-color-primary);
}
.color-fill {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  opacity: 0.95;
  transition: background 0.08s linear;
  pointer-events: none;
}
.color-thumb {
  position: absolute;
  top: 50%;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: #fff;
  border: 4px solid rgb(0 0 0 / 15%);
  transform: translate(-50%, -50%);
  box-shadow: 0 4px 12px rgb(0 0 0 / 25%);
  pointer-events: none;
}
.field-label {
  font-size: var(--ats-fs-body);
  color: var(--el-text-color-regular);
  font-weight: var(--ats-fw-medium);
}
.required {
  color: var(--el-color-danger);
  font-style: normal;
  margin-left: 2px;
}
.field-help {
  width: 100%;
  margin-top: 2px;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
@media (max-width: 759px) {
  .form-renderer :deep(.el-form) {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
