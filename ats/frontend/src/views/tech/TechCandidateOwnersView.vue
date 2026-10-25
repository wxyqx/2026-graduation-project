<!--
  【候选人负责人调整】技术管理端专用。
  候选人负责人默认 = 建档 / 上传简历录入的 HR，负责人能编辑该候选人的全部关卡；
  这里供技术管理员单个或批量变更负责人（也可以清空 = 暂无负责人，任意 HR 可编辑）。
  只展示姓名 / 手机号 / 当前负责人，不展示岗位与投递进度等招聘业务数据。
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { techCandidateOwnerApi } from '../../api/tech'

const keyword = ref('')
const options = ref([]) // 可选负责人（启用中的 HR）
const rows = ref([])
const selection = ref([])
const loading = ref(false)

const editVisible = ref(false)
const editTarget = ref(null) // null = 批量
const editForm = reactive({ owner_id: null })
const saving = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await techCandidateOwnerApi.list(keyword.value)
    options.value = data.options || []
    rows.value = data.items || []
    selection.value = []
  } finally {
    loading.value = false
  }
}

function openEdit(row) {
  editTarget.value = row
  editForm.owner_id = row ? row.owner_id : null
  editVisible.value = true
}

async function save() {
  saving.value = true
  try {
    if (editTarget.value) {
      await techCandidateOwnerApi.setOwner(editTarget.value.id, editForm.owner_id)
      ElMessage.success('负责人已更新')
    } else {
      const ids = selection.value.map((r) => r.id)
      const { updated } = await techCandidateOwnerApi.batchSetOwner(ids, editForm.owner_id)
      ElMessage.success(`已更新 ${updated} 位候选人的负责人`)
    }
    editVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

function ownerName(id) {
  return options.value.find((o) => o.id === id)?.name || null
}

onMounted(load)
</script>

<template>
  <div>
    <div class="page-header">
      <h2>候选人负责人</h2>
    </div>

    <el-alert
      type="info"
      show-icon
      :closable="false"
      title="负责人能编辑该候选人的全部关卡；非负责人的 HR 只能编辑自己负责的关卡，其余只读"
      description="负责人默认 = 建档或上传简历录入的 HR。这里可以单个或批量变更，也可清空（清空后任意 HR 可编辑）。"
      class="tip"
    />

    <section class="ats-panel">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="姓名 / 手机号"
          clearable
          style="width: 220px"
          @keyup.enter="load"
          @clear="load"
        />
        <el-button type="primary" @click="load">搜索</el-button>
        <div class="spacer" />
        <el-button type="primary" plain :disabled="!selection.length" @click="openEdit(null)">
          批量设置负责人{{ selection.length ? `（已选 ${selection.length} 人）` : '' }}
        </el-button>
      </div>

      <el-table
        :data="rows"
        v-loading="loading"
        @selection-change="(v) => (selection = v)"
        class="ats-table"
      >
        <el-table-column type="selection" width="44" />
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="name" label="姓名" min-width="120" show-overflow-tooltip />
        <el-table-column prop="phone" label="手机号" width="150" />
        <el-table-column label="当前负责人" min-width="140">
          <template #default="{ row }">
            <span v-if="row.owner_name">{{ row.owner_name }}</span>
            <span v-else class="muted">暂无（任意 HR 可编辑）</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">改负责人</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <el-dialog
      v-model="editVisible"
      :title="editTarget ? `改负责人：${editTarget.name || editTarget.id}` : `批量设置负责人（${selection.length} 人）`"
      class="ats-dialog-narrow"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item label="负责人">
          <el-select v-model="editForm.owner_id" clearable filterable placeholder="选择 HR（清空 = 暂无负责人）" style="width: 100%">
            <el-option v-for="o in options" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <p class="muted" style="margin: 0">
          清空负责人后，该候选人的资料与全部关卡任何 HR 都能编辑（首次编辑关卡的人会自动成为该关负责人）。
        </p>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
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
.spacer {
  flex: 1;
}
</style>
