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

const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    list.value = await positionApi.list()
  } finally {
    loading.value = false
  }
}
onMounted(load)

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
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>&nbsp;新建岗位
      </el-button>
    </div>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" border empty-text="还没有岗位，点右上角新建一个">
        <el-table-column prop="position_name" label="岗位名称" min-width="180">
          <template #default="{ row }">
            {{ row.position_name }}
            <el-tag v-if="positionExtras.has(row.id)" size="small" type="warning" effect="plain" style="margin-left: 6px">
              AI附加条件
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="owner" label="负责人" width="120">
          <template #default="{ row }">{{ row.owner || '—' }}</template>
        </el-table-column>
        <el-table-column label="岗位要求" min-width="280">
          <template #default="{ row }">
            <el-tooltip v-if="row.position_requirements" :content="row.position_requirements" placement="top" :show-after="300">
              <div class="ellipsis" style="max-width: 420px">{{ row.position_requirements }}</div>
            </el-tooltip>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="application_count" label="投递数" width="90" align="center" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" :disabled="row.application_count > 0" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId === null ? '新建岗位' : '编辑岗位'"
      width="1120px"
      top="6vh"
      destroy-on-close
      class="position-dialog"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="岗位名称" prop="position_name">
          <el-input v-model="form.position_name" placeholder="例：Java高级工程师" maxlength="100" />
        </el-form-item>
        <el-form-item label="负责人" prop="owner">
          <el-input v-model="form.owner" placeholder="招聘负责人，可不填" maxlength="100" />
        </el-form-item>
        <el-form-item label="岗位要求" prop="position_requirements">
          <el-input
            v-model="form.position_requirements"
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
.muted {
  color: var(--el-text-color-secondary);
}
/* 弹窗右下角可拖拽调整大小（拉宽 / 拉高），最小尺寸与最大尺寸做了限制避免拉坏 */
:deep(.el-dialog) {
  resize: both;
  overflow: auto;
  min-width: 560px;
  min-height: 360px;
  max-width: 96vw;
  max-height: 90vh;
}
.extra-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
  margin-top: 4px;
}
</style>
