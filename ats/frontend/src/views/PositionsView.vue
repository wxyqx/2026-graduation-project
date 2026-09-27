<!--
  【岗位管理页】表格列出所有岗位；右上角「新建岗位」；每行可编辑 / 删除。
  新建和编辑共用一个弹窗（el-dialog + el-form），靠 editingId 区分是新建还是编辑。
  删除前先确认；有投递记录的岗位后端会回 409，拦截器自动弹出中文提示。
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { inject, onMounted, reactive, ref } from 'vue'

import { positionApi } from '../api'
import { positionExtras } from '../stores/positionExtras'

const refreshStats = inject('refreshStats')

const all = ref([]) // 全部岗位（含暂不招）
const list = ref([]) // 按筛选显示出来的
const loading = ref(false)
const hiddenFilter = ref('') // '' = 全部 / 'no' = 只在招 / 'yes' = 只暂不招

function applyFilter() {
  if (hiddenFilter.value === 'no') list.value = all.value.filter((p) => !p.is_hidden)
  else if (hiddenFilter.value === 'yes') list.value = all.value.filter((p) => p.is_hidden)
  else list.value = all.value
}

async function load() {
  loading.value = true
  try {
    all.value = await positionApi.list(true) // 管理页要连隐藏的一起拿
    applyFilter()
  } finally {
    loading.value = false
  }
}
onMounted(load)

// 切换「招 / 暂不招」：点一下即时生效
async function toggleHidden(row) {
  const next = !row.is_hidden
  await positionApi.update(row.id, { is_hidden: next })
  ElMessage.success(next ? `「${row.position_name}」已设为暂不招，相关数据不再体现` : `「${row.position_name}」已恢复在招`)
  await load()
  refreshStats?.()
}

// ---- 新建 / 编辑弹窗 ----
const dialogVisible = ref(false)
const editingId = ref(null) // null = 新建，数字 = 编辑这个 id
const formRef = ref()
// ai_extra 不进数据库，只存浏览器（positionExtras）
const form = reactive({ position_name: '', owner: '', position_requirements: '', ai_extra: '' })
const rules = {
  position_name: [{ required: true, message: '请输入岗位名称', trigger: 'blur' }],
}
const saving = ref(false)

function openCreate() {
  editingId.value = null
  Object.assign(form, { position_name: '', owner: '', position_requirements: '', ai_extra: '' })
  dialogVisible.value = true
}
function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    position_name: row.position_name || '',
    owner: row.owner || '',
    position_requirements: row.position_requirements || '',
    ai_extra: positionExtras.get(row.id), // 从浏览器里读回上次填的附加条件
  })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    // 只把要进数据库的字段发给后端；ai_extra 单独存浏览器
    const payload = {
      position_name: form.position_name,
      owner: form.owner,
      position_requirements: form.position_requirements,
    }
    if (editingId.value === null) {
      const created = await positionApi.create(payload) // 后端返回带新 id，才能把附加条件挂在它名下
      positionExtras.set(created.id, form.ai_extra)
      ElMessage.success('岗位已创建')
    } else {
      await positionApi.update(editingId.value, payload)
      positionExtras.set(editingId.value, form.ai_extra)
      ElMessage.success('岗位已更新')
    }
    dialogVisible.value = false
    await load()
    refreshStats?.()
  } finally {
    saving.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除岗位「${row.position_name}」？`, '删除确认', { type: 'warning' })
  } catch {
    return // 点了取消
  }
  await positionApi.remove(row.id)
  positionExtras.remove(row.id) // 顺便清掉这个岗位在浏览器里存的附加条件
  ElMessage.success('已删除')
  await load()
  refreshStats?.()
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>岗位管理</h2>
      <div class="header-tools">
        <span class="muted">显示</span>
        <el-select v-model="hiddenFilter" size="default" style="width: 130px" @change="applyFilter">
          <el-option label="全部岗位" value="" />
          <el-option label="只在招" value="no" />
          <el-option label="只暂不招" value="yes" />
        </el-select>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>&nbsp;新建岗位
        </el-button>
      </div>
    </div>

    <section class="panel">
      <el-table
        :data="list"
        v-loading="loading"
        border
        :row-class-name="({ row }) => (row.is_hidden ? 'row-hidden' : '')"
        empty-text="还没有岗位，点右上角新建一个"
      >
        <el-table-column prop="position_name" label="岗位名称" min-width="200">
          <template #default="{ row }">
            <!-- 岗位名可能很长：单行截断，别把后面的标签挤走 -->
            <span class="ellipsis name-ellipsis">{{ row.position_name }}</span>
            <el-tag v-if="row.is_hidden" size="small" type="info" effect="dark" style="margin-left: 6px">已隐藏</el-tag>
            <el-tag v-if="positionExtras.has(row.id)" size="small" type="warning" effect="plain" style="margin-left: 6px">
              AI附加条件
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="招聘状态" width="110" align="center">
          <template #default="{ row }">
            <el-switch
              :model-value="!row.is_hidden"
              :aria-label="`招聘状态：${row.position_name}`"
              active-text="招"
              inactive-text="暂不招"
              inline-prompt
              @change="toggleHidden(row)"
            />
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="120">
          <template #default="{ row }">{{ row.owner || '—' }}</template>
        </el-table-column>
        <el-table-column label="岗位要求" min-width="280">
          <template #default="{ row }">
            <el-tooltip
              v-if="row.position_requirements"
              :content="row.position_requirements"
              placement="top"
              :show-after="300"
              :trigger="['hover', 'focus']"
            >
              <!-- tabindex：鼠标靠悬停看全文，键盘靠聚焦看，两条路都能读到完整要求 -->
              <div class="ellipsis" style="max-width: 420px" tabindex="0">{{ row.position_requirements }}</div>
            </el-tooltip>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="投递数" width="90" align="right">
          <template #default="{ row }"><span class="ats-nums">{{ row.application_count }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" :disabled="row.application_count > 0" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新建岗位' : '编辑岗位'"
      class="ats-dialog-full position-dialog"
      top="6vh"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="岗位名称" prop="position_name">
          <el-input
            v-model="form.position_name"
            name="position-name"
            autocomplete="off"
            placeholder="例：Java高级工程师"
            maxlength="100"
          />
        </el-form-item>
        <el-form-item label="负责人" prop="owner">
          <el-input
            v-model="form.owner"
            name="position-owner"
            autocomplete="name"
            placeholder="招聘负责人，可不填"
            maxlength="100"
          />
        </el-form-item>
        <el-form-item label="岗位要求" prop="position_requirements">
          <el-input
            v-model="form.position_requirements"
            name="position-requirements"
            autocomplete="off"
            type="textarea"
            :rows="12"
            maxlength="2000"
            show-word-limit
            placeholder="职位描述 / 任职要求。AI 筛简历时拿这段话比对，写得越具体越准"
          />
        </el-form-item>
        <el-form-item label="AI附加条件">
          <el-input
            v-model="form.ai_extra"
            name="position-ai-extra"
            autocomplete="off"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="给 AI 的额外限制，例：只要 985/211 院校；必须有医疗行业项目经验；不接受外包背景"
          />
          <div class="extra-hint">
            这段文字<b>不保存到数据库</b>，只存在本机浏览器；仅在「AI 录入简历」筛这个岗位时作为额外限制一并发给 AI，刷新后仍保留。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* 弹窗右下角可拖拽调整大小（拉宽 / 拉高），最小尺寸与最大尺寸做了限制避免拉坏。
   最小宽度跟随视口收敛，免得窄屏下 560px 撑出横向滚动条。 */
:deep(.el-dialog) {
  resize: both;
  overflow: auto;
  min-width: min(560px, calc(100vw - 32px));
  min-height: min(360px, calc(100vh - 32px));
  max-width: calc(100vw - 32px);
  max-height: 90vh;
}
/* 暂不招的岗位整行置灰 */
:deep(.row-hidden) {
  color: var(--el-text-color-placeholder);
  background: var(--el-fill-color-light);
}
.header-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}
.extra-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-top: 4px;
}
/* 岗位名截断：给它一个可收缩的最大宽度，多余的省略号 */
.name-ellipsis {
  display: inline-block;
  max-width: 160px;
  vertical-align: bottom;
}
</style>
