<!--
  【候选人管理页】所有来应聘的人。
    右上角：按姓名搜索
    表格：姓名 / 备注 / 名下投递数 / 录入时间 / 操作（删除）
    删除：会连同他名下的投递记录一起删掉（级联），删除前弹强确认，说明会删几条投递。

  「录入时间」格式化一下更好看。
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { inject, onMounted, ref } from 'vue'

import { candidateApi } from '../api'
import { fmtTime } from '../utils/format'

const refreshStats = inject('refreshStats')

const list = ref([])
const loading = ref(false)
const keyword = ref('')

async function load() {
  loading.value = true
  try {
    list.value = await candidateApi.list(keyword.value.trim() || undefined)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function search() {
  load()
}
function clearSearch() {
  keyword.value = ''
  load()
}

async function remove(row) {
  const n = row.application_count || 0
  const tip = n > 0 ? `，以及他名下的 ${n} 条投递记录` : ''
  try {
    await ElMessageBox.confirm(
      `将删除候选人「${row.name}」${tip}。此操作不可恢复，确定删除？`,
      '删除候选人',
      { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' },
    )
  } catch {
    return // 点了取消
  }
  await candidateApi.remove(row.id)
  ElMessage.success(`已删除「${row.name}」${n > 0 ? `及其 ${n} 条投递` : ''}`)
  await load()
  refreshStats?.()
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>候选人管理</h2>
      <el-input
        v-model="keyword"
        placeholder="按姓名搜索"
        clearable
        style="width: 220px"
        @keyup.enter="search"
        @clear="clearSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <el-card shadow="never">
      <el-table :data="list" v-loading="loading" stripe empty-text="暂无候选人">
        <el-table-column prop="name" label="姓名" min-width="120" />
        <el-table-column prop="remark" label="备注" min-width="180">
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </el-table-column>
        <el-table-column label="名下投递" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.application_count > 0 ? 'primary' : 'info'" size="small" effect="plain">
              {{ row.application_count }} 条
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="录入时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
