<!--
  【关卡负责人调整】技术管理端专用。
  每条投递的每个关卡都有一个 HR 负责人（首次编辑该关的 HR 自动认领）；
  阶段负责人只能编辑本关，其他关只读。这里按投递逐关指派 / 更换 / 清空负责人。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { techStageOwnerApi } from '../../api/tech'
import { STATUS_LABEL, STATUS_TYPE } from '../../constants'

const keyword = ref('')
const options = ref([]) // 可选负责人（启用中的 HR）
const stages = ref([]) // 7 关定义
const rows = ref([])
const loading = ref(false)

const editVisible = ref(false)
const editRow = ref(null)
const editForm = reactive({ owners: {} })
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await techStageOwnerApi.list(keyword.value)
    options.value = data.options || []
    stages.value = data.stages || []
    rows.value = data.items || []
  } finally {
    loading.value = false
  }
}

function ownerName(row, stage) {
  return row.stage_owners?.[stage]?.name || null
}

function openEdit(row) {
  editRow.value = row
  editForm.owners = {}
  for (const st of stages.value) {
    editForm.owners[st.value] = row.stage_owners?.[st.value]?.user_id ?? null
  }
  editVisible.value = true
}

const changedCount = computed(() => {
  if (!editRow.value) return 0
  return stages.value.filter((st) => (editForm.owners[st.value] ?? null) !== (editRow.value.stage_owners?.[st.value]?.user_id ?? null)).length
})

async function save() {
  saving.value = true
  try {
    const { changed } = await techStageOwnerApi.setOwners(editRow.value.id, editForm.owners)
    ElMessage.success(changed ? `已更新 ${changed} 关的负责人` : '没有变化')
    editVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>关卡负责人</h2>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="阶段负责人只能编辑自己那一关，其他关只读；候选人负责人则能编辑全部关卡"
      description="负责人默认由首次编辑该关的 HR 自动认领，这里可以按投递逐关指派 / 更换 / 清空。"
      class="tip"
    />

    <section class="ats-panel">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="候选人姓名 / 手机号 / 岗位名"
          clearable
          style="width: 240px"
          @keyup.enter="load"
          @clear="load"
        />
        <el-button type="primary" @click="load">搜索</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" class="ats-table">
        <el-table-column prop="id" label="投递" width="80" />
        <el-table-column prop="candidate_name" label="候选人" min-width="110" show-overflow-tooltip />
        <el-table-column prop="position_name" label="岗位" min-width="140" show-overflow-tooltip />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="STATUS_TYPE[row.overall_status]" size="small" effect="light">
              {{ STATUS_LABEL[row.overall_status] }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="各关负责人" min-width="260">
          <template #default="{ row }">
            <span v-if="Object.keys(row.stage_owners || {}).length" class="ats-nums owner-line">
              <span v-for="st in stages" :key="st.value" class="owner-chip">
                <span v-if="ownerName(row, st.value)">{{ st.label }}·{{ ownerName(row, st.value) }}</span>
              </span>
            </span>
            <span v-else class="muted">暂无认领</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">调整负责人</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog
      v-model="editVisible"
      :title="`调整关卡负责人：${editRow?.candidate_name || ''} · ${editRow?.position_name || ''}`"
      width="560px"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item v-for="st in stages" :key="st.value" :label="st.label">
          <el-select
            v-model="editForm.owners[st.value]"
            clearable
            filterable
            placeholder="未认领（任意 HR 可编辑）"
            style="width: 100%"
          >
            <el-option v-for="o in options" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <p class="muted" style="margin: 0">
          清空 = 该关回到「未认领」，任何 HR 都能编辑（谁先编辑谁认领）。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" :disabled="!changedCount" @click="save">
          保存{{ changedCount ? `（${changedCount} 处变更）` : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tip {
  margin-bottom: var(--ats-sp-4);
}
.toolbar {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
  margin-bottom: var(--ats-sp-3);
}
.owner-line {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12px;
}
.owner-chip:empty {
  display: none;
}
</style>
