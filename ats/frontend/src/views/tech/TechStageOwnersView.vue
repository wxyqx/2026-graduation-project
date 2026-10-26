<!--
  【关卡负责人调整】技术管理端专用。
  负责人按「岗位 × 关卡」指派：某岗位所有候选人的某一关都由同一位 HR 负责（如全部候选人的专业面都是一个人），
  不用一个投递一个投递地去选。对该岗位之后新建的投递同样生效。
  例外：个别投递若已被 HR 首次编辑自动认领，以投递级记录为准（这里不显示、也不覆盖）。
-->
<script setup>
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { techStageOwnerApi } from '../../api/tech'

const keyword = ref('')
const options = ref([]) // 可选负责人（启用中的 HR）
const stages = ref([]) // 7 关定义
const rows = ref([]) // 岗位列表
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
  return stages.value.filter(
    (st) => (editForm.owners[st.value] ?? null) !== (editRow.value.stage_owners?.[st.value]?.user_id ?? null),
  ).length
})

async function save() {
  saving.value = true
  try {
    const { changed } = await techStageOwnerApi.setOwners(editRow.value.id, editForm.owners)
    ElMessage.success(changed ? `已更新 ${changed} 关的负责人，对该岗位全部候选人生效` : '没有变化')
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
      title="按岗位指派：某岗位的某一关由谁负责，该岗位全部候选人一起生效"
      description="例如把「产品经理」的专业面指给王五，则该岗位所有候选人（含之后新建的投递）的专业面都由王五负责。
        只有未指派的关才由 HR 首次编辑时自动认领。"
      class="tip"
    />

    <section class="ats-panel">
      <div class="toolbar">
        <el-input
          v-model="keyword"
          placeholder="岗位名"
          clearable
          style="width: 240px"
          @keyup.enter="load"
          @clear="load"
        />
        <el-button type="primary" @click="load">搜索</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" class="ats-table">
        <el-table-column prop="id" label="岗位" width="80" />
        <el-table-column prop="position_name" label="岗位名称" min-width="180" show-overflow-tooltip />
        <el-table-column label="招聘中" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_hidden ? 'info' : 'success'" size="small" effect="plain">
              {{ row.is_hidden ? '暂不招' : '在招' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="各关负责人" min-width="300">
          <template #default="{ row }">
            <span v-if="Object.keys(row.stage_owners || {}).length" class="ats-nums owner-line">
              <span v-for="st in stages" :key="st.value" class="owner-chip">
                <span v-if="ownerName(row, st.value)">{{ st.label }}·{{ ownerName(row, st.value) }}</span>
              </span>
            </span>
            <span v-else class="muted">未指派（HR 编辑时自动认领）</span>
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
      :title="`调整关卡负责人：${editRow?.position_name || ''}（对该岗位全部候选人生效）`"
      width="560px"
      destroy-on-close
    >
      <el-form label-width="90px">
        <el-form-item v-for="st in stages" :key="st.value" :label="st.label">
          <el-select
            v-model="editForm.owners[st.value]"
            clearable
            filterable
            placeholder="未指派（HR 编辑时自动认领）"
            style="width: 100%"
          >
            <el-option v-for="o in options" :key="o.id" :label="o.name" :value="o.id" />
          </el-select>
        </el-form-item>
        <p class="muted" style="margin: 0">
          清空 = 该关回到「未指派」，HR 首次编辑时自动认领。
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
