<!--
  【候选人管理页】所有来应聘的人。
    顶部搜索栏：姓名（模糊）/ 备注（模糊）/ 有无投递，可搜索、可重置
    表格：姓名 / 备注 / 名下投递数 / 录入时间 / 操作（详情、删除）
    点姓名或「详情」→ 右侧抽屉：基础信息 + 他投了哪些岗位（可跳投递详情）
    删除：会连同他名下的投递记录一起删掉（级联），删除前弹强确认。
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { inject, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { applicationApi, candidateApi } from '../api'
import { STAGE_LABEL, STATUS_LABEL, STATUS_TYPE } from '../constants'
import { fmtTime } from '../utils/format'

const router = useRouter()
const refreshStats = inject('refreshStats')

const list = ref([])
const loading = ref(false)

// ---- 搜索栏 ----
const filters = reactive({ name: '', remark: '', has_application: '' })

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.name.trim()) params.name = filters.name.trim()
    if (filters.remark.trim()) params.remark = filters.remark.trim()
    if (filters.has_application) params.has_application = filters.has_application
    list.value = await candidateApi.list(params)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function resetFilters() {
  Object.assign(filters, { name: '', remark: '', has_application: '' })
  load()
}

// ---- 详情抽屉 ----
const drawerVisible = ref(false)
const detail = ref(null) // 当前查看的候选人
const apps = ref([]) // 他名下的投递
const appsLoading = ref(false)

async function openDetail(row) {
  detail.value = row
  drawerVisible.value = true
  appsLoading.value = true
  try {
    apps.value = await applicationApi.list({ can_id: row.id })
  } finally {
    appsLoading.value = false
  }
}

function gotoApplication(appId) {
  router.push({ name: 'application-detail', params: { id: appId } })
}

// ---- 删除 ----
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
  if (detail.value?.id === row.id) drawerVisible.value = false
  await load()
  refreshStats?.()
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>候选人管理</h2>
      <span class="muted">共 {{ list.length }} 人</span>
    </div>

    <!-- 搜索栏 -->
    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="姓名">
          <el-input
            v-model="filters.name"
            placeholder="姓名含…"
            clearable
            style="width: 150px"
            @keyup.enter="load"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="filters.remark"
            placeholder="如 内推 / 二批"
            clearable
            style="width: 150px"
            @keyup.enter="load"
          />
        </el-form-item>
        <el-form-item label="投递情况">
          <el-select v-model="filters.has_application" placeholder="全部" clearable style="width: 140px">
            <el-option label="有投递记录" value="yes" />
            <el-option label="暂未投递" value="no" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">
            <el-icon><Search /></el-icon>&nbsp;搜索
          </el-button>
          <el-button @click="resetFilters">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <section class="panel">
      <el-table :data="list" v-loading="loading" border empty-text="没有符合条件的候选人">
        <el-table-column label="姓名" min-width="130">
          <template #default="{ row }">
            <el-link type="primary" :underline="false" @click="openDetail(row)">{{ row.name }}</el-link>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="160">
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </el-table-column>
        <el-table-column label="名下投递" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="row.application_count > 0 ? 'primary' : 'info'" size="small" effect="plain">
              <span class="ats-nums">{{ row.application_count }}</span> 条
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="录入时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 候选人详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="detail ? `候选人：${detail.name}` : '候选人详情'" size="620px">
      <template v-if="detail">
        <el-descriptions :column="2" border size="small">
          <el-descriptions-item label="姓名">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '—' }}</el-descriptions-item>
          <el-descriptions-item label="录入时间">{{ fmtTime(detail.create_time) }}</el-descriptions-item>
          <el-descriptions-item label="名下投递">
            {{ detail.application_count }} 条
          </el-descriptions-item>
        </el-descriptions>

        <div class="section-title">投递记录</div>
        <el-table :data="apps" v-loading="appsLoading" border size="small" empty-text="还没有投递记录">
          <el-table-column prop="position_name" label="岗位" min-width="170" />
          <el-table-column label="当前阶段" width="100">
            <template #default="{ row }">
              <el-tag effect="plain" size="small">{{ STAGE_LABEL[row.current_stage] || row.current_stage }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="STATUS_TYPE[row.overall_status]" size="small">{{ STATUS_LABEL[row.overall_status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="AI 结论" width="90">
            <template #default="{ row }">
              <el-tag v-if="row.ai_result" size="small" :type="row.ai_result === 'pass' ? 'success' : 'danger'" effect="light">
                {{ row.ai_result === 'pass' ? '通过' : '淘汰' }}
              </el-tag>
              <span v-else class="muted">—</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="gotoApplication(row.id)">查看</el-button>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template #footer>
        <el-button @click="drawerVisible = false">关闭</el-button>
        <el-button v-if="detail" type="danger" plain @click="remove(detail)">删除该候选人</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.section-title {
  margin: 18px 0 8px;
  font-weight: 600;
  font-size: 14px;
}
</style>
