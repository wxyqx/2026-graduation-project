<!--
  【系统设置页】
  AI 筛选 API 管理：系统不会自己筛简历，要请外面的大模型帮忙。这里维护一组「帮谁干活」的配置。
    表格：名称 / 接口地址 / 模型 / 是否启用（开关，可同时开多个）/ 操作
    右上「新建配置」；行内可编辑、删除；支持多个同时启用。
  「在哪里申请密钥」折叠帮助给新手看。
  底部：主题说明卡（主题开关在顶栏右侧）。
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { aiConfigApi } from '../api'

const list = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    list.value = await aiConfigApi.list()
  } finally {
    loading.value = false
  }
}
onMounted(load)

// ---- 新建 / 编辑弹窗 ----
const dialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref()
const form = reactive({ name: '', base_url: '', api_key: '', model: '', is_enabled: false })
const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  base_url: [
    { required: true, message: '请输入接口地址', trigger: 'blur' },
    { type: 'url', message: '地址格式不对（要 http:// 或 https:// 开头）', trigger: 'blur' },
  ],
  api_key: [{ required: true, message: '请输入密钥', trigger: 'blur' }],
  model: [{ required: true, message: '请输入模型名', trigger: 'blur' }],
}
const saving = ref(false)

function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', base_url: '', api_key: '', model: '', is_enabled: false })
  dialogVisible.value = true
}
function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    base_url: row.base_url,
    api_key: row.api_key,
    model: row.model,
    is_enabled: row.is_enabled,
  })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editingId.value === null) {
      await aiConfigApi.create({ ...form })
      ElMessage.success('配置已添加')
    } else {
      await aiConfigApi.update(editingId.value, { ...form })
      ElMessage.success('配置已更新')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function toggle(row) {
  if (row.is_enabled) await aiConfigApi.disable(row.id)
  else await aiConfigApi.enable(row.id)
  ElMessage.success(row.is_enabled ? '已停用' : '已启用')
  await load()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除配置「${row.name}」？`, '删除配置', { type: 'warning' })
  } catch {
    return
  }
  await aiConfigApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}

const helpVisible = ref(false)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>系统设置</h2>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>&nbsp;新建配置
      </el-button>
    </div>

    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>AI 筛选 API 管理</span>
          <el-button link type="primary" size="small" @click="helpVisible = !helpVisible">
            {{ helpVisible ? '收起帮助' : '哪里申请密钥？' }}
          </el-button>
        </div>
      </template>

      <el-collapse-transition>
        <div v-if="helpVisible" class="help">
          <p>支持所有「OpenAI 兼容」的大模型服务，任选一家注册并创建 API Key：</p>
          <table>
            <tr><th>服务</th><th>接口地址（base_url）</th><th>模型名示例</th></tr>
            <tr><td>智谱 GLM</td><td>https://open.bigmodel.cn/api/paas/v4</td><td>glm-4-flash（免费）</td></tr>
            <tr><td>通义千问</td><td>https://dashscope.aliyuncs.com/compatible-mode/v1</td><td>qwen-turbo</td></tr>
            <tr><td>DeepSeek</td><td>https://api.deepseek.com/v1</td><td>deepseek-chat</td></tr>
          </table>
          <p class="muted">
            base_url 填到 /v4 或 /v1 即可，系统自动补 /chat/completions。可加多个并同时启用，
            AI 录入时在启用配置间轮流使用，某家出错会自动换另一家重试。
          </p>
        </div>
      </el-collapse-transition>

      <el-table :data="list" v-loading="loading" empty-text="还没有 AI 配置，点右上角新建">
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="base_url" label="接口地址" min-width="240" show-overflow-tooltip />
        <el-table-column prop="model" label="模型" width="160" />
        <el-table-column label="启用" width="100" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.is_enabled" @change="toggle(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" style="margin-top: 14px">
      <template #header>主题偏好</template>
      <p class="muted">主题切换在页面右上角（白天 / 黑夜 / 护眼），选择自动保存在本浏览器，刷新后保持。</p>
    </el-card>

    <!-- 新建/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="editingId === null ? '新建 AI 配置' : '编辑 AI 配置'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="配置名称" prop="name">
          <el-input v-model="form.name" placeholder="例：GLM免费版（自己认得就行）" maxlength="50" />
        </el-form-item>
        <el-form-item label="接口地址" prop="base_url">
          <el-input v-model="form.base_url" placeholder="例：https://open.bigmodel.cn/api/paas/v4" maxlength="255" />
        </el-form-item>
        <el-form-item label="密钥" prop="api_key">
          <el-input v-model="form.api_key" placeholder="去 AI 平台的 API Keys 页面申请" show-password maxlength="255" />
        </el-form-item>
        <el-form-item label="模型名" prop="model">
          <el-input v-model="form.model" placeholder="例：glm-4-flash（填 /v4 系列模型时照抄平台文档）" maxlength="100" />
        </el-form-item>
        <el-form-item label="立刻启用">
          <el-switch v-model="form.is_enabled" />
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
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.help {
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  padding: 4px 16px;
  margin-bottom: 14px;
  font-size: 13px;
}
.help table {
  border-collapse: collapse;
  width: 100%;
  margin: 8px 0;
}
.help td,
.help th {
  border: 1px solid var(--el-border-color-lighter);
  padding: 6px 10px;
  text-align: left;
}
.muted {
  color: var(--el-text-color-secondary);
}
</style>
