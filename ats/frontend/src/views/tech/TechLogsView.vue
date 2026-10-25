<script setup>
import { onMounted, reactive, ref } from 'vue'

import { techLogApi } from '../../api/tech'
import { fmtTime } from '../../utils/format'

const list = ref([])
const total = ref(0)
const loading = ref(false)
const filters = reactive({ role: '', action: '', keyword: '' })
const page = ref(1)
const pageSize = ref(20)

const ACTION_LABEL = {
  login: '登录',
  create: '新建',
  update: '修改',
  delete: '删除',
  reset_password: '重置密码',
  export: '导出',
  backup: '备份',
  config_change: '配置变更',
}
const ROLE_LABEL = { candidate: '候选人', hr: 'HR', admin: '技术管理员' }

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize.value }
    if (filters.role) params.role = filters.role
    if (filters.action) params.action = filters.action
    if (filters.keyword.trim()) params.keyword = filters.keyword.trim()
    const data = await techLogApi.list(params)
    list.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}
onMounted(load)

function search() {
  page.value = 1
  load()
}

function resetFilters() {
  Object.assign(filters, { role: '', action: '', keyword: '' })
  search()
}

function onPageChange(p) {
  page.value = p
  load()
}

function detailText(detail) {
  if (detail === null || detail === undefined) return '—'
  if (typeof detail === 'string') return detail
  return JSON.stringify(detail)
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>操作日志</h2>
      <span class="muted">共 {{ total }} 条</span>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="角色">
          <el-select v-model="filters.role" placeholder="全部" clearable style="width: 130px">
            <el-option label="候选人" value="candidate" />
            <el-option label="HR" value="hr" />
            <el-option label="技术管理员" value="admin" />
          </el-select>
        </el-form-item>
        <el-form-item label="动作">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width: 140px">
            <el-option v-for="(label, value) in ACTION_LABEL" :key="value" :label="label" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="关键字">
          <el-input v-model="filters.keyword" placeholder="用户名或详情" clearable style="width: 200px" @keyup.enter="search" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search"><el-icon><Search /></el-icon>&nbsp;搜索</el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <section class="ats-panel">
      <el-table :data="list" v-loading="loading" border size="small" empty-text="还没有日志">
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="用户" min-width="130">
          <template #default="{ row }">{{ row.username || '—' }}</template>
        </el-table-column>
        <el-table-column label="角色" width="100">
          <template #default="{ row }">{{ ROLE_LABEL[row.role] || row.role || '—' }}</template>
        </el-table-column>
        <el-table-column label="动作" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ ACTION_LABEL[row.action] || row.action }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="对象" width="150">
          <template #default="{ row }">
            {{ row.target_type || '—' }}<span v-if="row.target_id"> #{{ row.target_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="220" show-overflow-tooltip>
          <template #default="{ row }"><span class="detail">{{ detailText(row.detail) }}</span></template>
        </el-table-column>
        <el-table-column prop="ip" label="IP" width="130" />
      </el-table>
      <div class="pager">
        <el-pagination
          :current-page="page"
          :page-size="pageSize"
          :total="total"
          layout="prev, pager, next, total"
          @current-change="onPageChange"
        />
      </div>
    </section>
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: var(--ats-sp-3);
}
.detail {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
</style>
