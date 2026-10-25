<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { techAccountApi } from '../../api/tech'
import { techAuth } from '../../stores/techAuth'
import { fmtTime } from '../../utils/format'

const list = ref([])
const loading = ref(false)
const filters = reactive({ role: '', status: '', keyword: '' })

const ROLE_LABEL = { candidate: '候选人', hr: 'HR', admin: '技术管理员' }
const ROLE_TYPE = { candidate: 'success', hr: 'primary', admin: 'warning' }

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.role) params.role = filters.role
    if (filters.status) params.status = filters.status
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    list.value = await techAccountApi.list(params)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function resetFilters() {
  Object.assign(filters, { role: '', status: '', keyword: '' })
  load()
}

// ---- 新建 HR / 技术管理员 ----
const createVisible = ref(false)
const createRef = ref()
const creating = ref(false)
const createForm = reactive({ role: 'hr', username: '', password: 'admin' })
const createRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入初始密码', trigger: 'blur' }],
}

function openCreate() {
  Object.assign(createForm, { role: 'hr', username: '', password: 'admin' })
  createVisible.value = true
}

async function submitCreate() {
  await createRef.value.validate()
  creating.value = true
  try {
    await techAccountApi.create({ ...createForm })
    ElMessage.success('账号已创建')
    createVisible.value = false
    await load()
  } finally {
    creating.value = false
  }
}

async function toggleStatus(row) {
  const next = !row.is_active
  if (!next) {
    try {
      await ElMessageBox.confirm(`停用「${row.name}」后该账号将无法登录。确定？`, '停用账号', { type: 'warning' })
    } catch {
      return
    }
  }
  await techAccountApi.setStatus(row.id, next)
  ElMessage.success(next ? '已启用' : '已停用')
  await load()
}

async function resetPassword(row) {
  try {
    await ElMessageBox.confirm(
      `把「${row.name}」的密码重置为默认密码 admin？`,
      '重置密码',
      { type: 'warning' },
    )
  } catch {
    return
  }
  await techAccountApi.resetPassword(row.id)
  ElMessage.success('密码已重置为 admin')
}

function isSelf(row) {
  return techAuth.user.value?.id === row.id
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>账号管理</h2>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>&nbsp;新建 HR / 技术管理员
      </el-button>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="角色">
          <el-select v-model="filters.role" placeholder="全部" clearable style="width: 140px">
            <el-option label="候选人" value="candidate" />
            <el-option label="HR" value="hr" />
            <el-option label="技术管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width: 120px">
            <el-option label="启用" value="active" />
            <el-option label="停用" value="inactive" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="filters.keyword" placeholder="用户名 / 姓名 / 手机号" clearable style="width: 220px" @keyup.enter="load" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load"><el-icon><Search /></el-icon>&nbsp;搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <section class="ats-panel">
      <el-table :data="list" v-loading="loading" border empty-text="没有符合条件的账号">
        <el-table-column label="名称" min-width="150">
          <template #default="{ row }">
            {{ row.name }}
            <el-tag v-if="isSelf(row)" size="small" type="info" effect="plain" style="margin-left: 6px">当前</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="用户名" min-width="150">
          <template #default="{ row }">{{ row.username || '（手机号账号）' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="110">
          <template #default="{ row }">
            <el-tag :type="ROLE_TYPE[row.role]" size="small" effect="plain">{{ ROLE_LABEL[row.role] || row.role }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="手机号" width="130">
          <template #default="{ row }">{{ row.phone || '—' }}</template>
        </el-table-column>
        <el-table-column label="最近登录" width="150">
          <template #default="{ row }">{{ fmtTime(row.last_login_time) || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
              {{ row.is_active ? '启用' : '停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link :type="row.is_active ? 'danger' : 'success'" :disabled="isSelf(row)" @click="toggleStatus(row)">
              {{ row.is_active ? '停用' : '启用' }}
            </el-button>
            <el-button link type="primary" @click="resetPassword(row)">重置密码</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog v-model="createVisible" title="新建账号" class="ats-dialog-narrow" destroy-on-close>
      <el-form ref="createRef" :model="createForm" :rules="createRules" label-width="90px">
        <el-form-item label="角色">
          <el-radio-group v-model="createForm.role">
            <el-radio value="hr">HR</el-radio>
            <el-radio value="admin">技术管理员</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="用户名" prop="username">
          <el-input v-model="createForm.username" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="初始密码" prop="password">
          <el-input v-model="createForm.password" placeholder="默认 admin" />
        </el-form-item>
      </el-form>
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="候选人账号不在这里创建"
        description="HR 在候选人档案里填手机号后，系统会自动开通候选人账号。"
      />
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
