<script setup>
import { ElMessage } from 'element-plus'
import { ref } from 'vue'

import { techBackupApi } from '../../api/tech'

const exporting = ref(false)
const last = ref(null)

async function exportBackup() {
  exporting.value = true
  try {
    const res = await techBackupApi.download()
    last.value = res
    ElMessage.success(`备份已下载：${res.filename}`)
  } finally {
    exporting.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>备份导出</h2>
    </div>

    <section class="ats-panel">
      <h3 class="title">导出全库 ZIP</h3>
      <p class="muted">
        备份包含 12 张表的 CSV、候选人文件原件和一份 manifest 清单。
        恢复是手工操作：解压后按 CSV 导回数据库，文件放回 Candidate_File 表。
      </p>
      <el-alert
        type="warning"
        show-icon
        :closable="false"
        title="备份包含候选人个人信息与简历原件，请只保存在可信位置"
        description="导出动作会写入操作日志。"
        class="warn"
      />
      <el-button type="primary" size="large" :loading="exporting" @click="exportBackup">
        <el-icon><Download /></el-icon>&nbsp;导出备份 ZIP
      </el-button>
      <p v-if="last" class="last">
        最近导出：<b>{{ last.filename }}</b>（{{ last.rows }} 行数据）
      </p>
    </section>
  </div>
</template>

<style scoped>
.title {
  margin: 0 0 var(--ats-sp-2);
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
}
.warn {
  margin: var(--ats-sp-3) 0;
}
.last {
  margin-top: var(--ats-sp-3);
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-secondary);
}
</style>
