<script setup>
import { onMounted, ref } from 'vue'

import { techOverviewApi } from '../../api/tech'
import { fmtTime } from '../../utils/format'

const data = ref(null)
const loading = ref(false)

// 磁盘/库体积告警（v3.17 P1-15）：BLOB 膨胀与磁盘占满是最可预期的死法
const storage = ref(null)

async function load() {
  loading.value = true
  try {
    data.value = await techOverviewApi.get()
    try {
      storage.value = await techOverviewApi.storage()
    } catch {
      storage.value = null
    }
  } finally {
    loading.value = false
  }
}
onMounted(load)

const STORAGE_LEVEL_TEXT = { ok: '', warn: '备份盘剩余空间不足 20%，建议清理', danger: '备份盘剩余空间不足 10%，备份可能失败，请立即清理' }

function fmtBytes(n) {
  if (!n && n !== 0) return '—'
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`
}

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
</script>

<template>
  <div v-loading="loading">
    <div class="page-header">
      <h2>运行概览</h2>
      <el-button size="small" @click="load">刷新</el-button>
    </div>

    <template v-if="data">
      <div class="stat-grid">
        <div class="ats-panel stat-card">
          <div class="stat-label">账号</div>
          <div class="stat-num">{{ data.users.total }}</div>
          <div class="stat-sub">
            HR {{ data.users.hr }} · 技术 {{ data.users.admin }} · 候选人 {{ data.users.candidate }}
            <span v-if="data.users.inactive"> · 停用 {{ data.users.inactive }}</span>
          </div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">投递</div>
          <div class="stat-num">{{ data.business.applications }}</div>
          <div class="stat-sub">
            进行中 {{ data.business.pending }} · 候选人投递 {{ data.business.portal_applications }}
          </div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">候选人 / 岗位</div>
          <div class="stat-num">{{ data.business.candidates }} / {{ data.business.positions }}</div>
          <div class="stat-sub">在招 {{ data.business.positions - data.business.positions_hidden }} · 暂不招 {{ data.business.positions_hidden }}</div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">数据库体积</div>
          <div class="stat-num">{{ fmtBytes(data.system.db_bytes) }}</div>
          <div class="stat-sub">近 7 天日志 {{ data.system.logs_7d }} 条</div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">AI 配置</div>
          <div class="stat-num">{{ data.system.ai_enabled }} / {{ data.system.ai_configs }}</div>
          <div class="stat-sub">启用 / 总数</div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">候选人文件</div>
          <div class="stat-num">{{ data.system.files }}</div>
          <div class="stat-sub">{{ fmtBytes(data.system.file_bytes) }}</div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">表单</div>
          <div class="stat-num">{{ data.system.form_templates }}</div>
          <div class="stat-sub">答卷 {{ data.system.form_submissions }} 份</div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">录用 / 淘汰</div>
          <div class="stat-num">{{ data.business.pass }} / {{ data.business.fail }}</div>
          <div class="stat-sub">全部投递的终局</div>
        </div>
        <div class="ats-panel stat-card">
          <div class="stat-label">磁盘余量（备份盘）</div>
          <div class="stat-num" :style="storage && storage.level !== 'ok' ? 'color: var(--el-color-' + (storage.level === 'danger' ? 'danger' : 'warning') + ')' : ''">
            {{ storage ? fmtBytes(storage.backup_free_bytes) : '—' }}
          </div>
          <div class="stat-sub">
            {{ storage ? `库占 ${fmtBytes(storage.db_size_bytes)}（BLOB ${fmtBytes(storage.file_blob_bytes)}·${storage.file_count} 份）` : '' }}
            <span v-if="storage && STORAGE_LEVEL_TEXT[storage.level]">{{ STORAGE_LEVEL_TEXT[storage.level] }}</span>
          </div>
        </div>
      </div>

      <section class="ats-panel recent">
        <div class="card-header">
          <span class="ats-panel-title" style="margin: 0">最近操作</span>
          <router-link to="/tech/logs" class="link">查看全部</router-link>
        </div>
        <el-table :data="data.recent_logs" border size="small" empty-text="还没有日志">
          <el-table-column label="时间" width="160">
            <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
          </el-table-column>
          <el-table-column label="用户" min-width="130">
            <template #default="{ row }">{{ row.username || '—' }}</template>
          </el-table-column>
          <el-table-column label="角色" width="90">
            <template #default="{ row }">{{ row.role || '—' }}</template>
          </el-table-column>
          <el-table-column label="动作" width="100">
            <template #default="{ row }">{{ ACTION_LABEL[row.action] || row.action }}</template>
          </el-table-column>
          <el-table-column label="对象" min-width="140">
            <template #default="{ row }">{{ row.target_type || '—' }}<span v-if="row.target_id"> #{{ row.target_id }}</span></template>
          </el-table-column>
          <el-table-column prop="ip" label="IP" width="130" />
        </el-table>
      </section>
    </template>
  </div>
</template>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--ats-sp-3);
  margin-bottom: var(--ats-sp-4);
}
.stat-card {
  padding: var(--ats-sp-4);
}
.stat-label {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.stat-num {
  margin: 6px 0 4px;
  font-size: var(--ats-fs-stat);
  font-weight: var(--ats-fw-bold);
  font-variant-numeric: var(--ats-nums);
  color: var(--el-text-color-primary);
}
.stat-sub {
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
  line-height: 1.5;
}
.recent {
  padding: var(--ats-sp-4);
}
.link {
  color: var(--el-color-primary);
  font-size: var(--ats-fs-label);
  text-decoration: none;
}
@media (max-width: 1100px) {
  .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
