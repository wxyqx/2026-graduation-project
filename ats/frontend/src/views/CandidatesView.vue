<!--
  【候选人管理页】所有来应聘的人。
    顶部搜索栏：姓名 / 手机号 / 账号状态 / 备注 / 有无投递
    表格：姓名 / 手机号 / 账号 / 备注 / 名下投递 / 录入时间 / 操作
    详情抽屉：基本信息、文件（HR 上传）、表单答卷、投递记录
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { inject, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { applicationApi, candidateApi, formTemplateApi } from '../api'
import { STAGE_LABEL, STATUS_LABEL, STATUS_TYPE } from '../constants'
import PortalFormRenderer from '../components/PortalFormRenderer.vue'
import { fmtTime } from '../utils/format'

const router = useRouter()
const refreshStats = inject('refreshStats')

const list = ref([])
const loading = ref(false)

// ---- 搜索栏 ----
const filters = reactive({ name: '', phone: '', has_account: '', remark: '', has_application: '' })

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.name.trim()) params.name = filters.name.trim()
    if (filters.phone.trim()) params.phone = filters.phone.trim()
    if (filters.has_account) params.has_account = filters.has_account
    if (filters.remark.trim()) params.remark = filters.remark.trim()
    if (filters.has_application) params.has_application = filters.has_application
    list.value = await candidateApi.list(params)
  } finally {
    loading.value = false
  }
}
onMounted(load)

function resetFilters() {
  Object.assign(filters, { name: '', phone: '', has_account: '', remark: '', has_application: '' })
  load()
}

// ---- 新建 / 编辑 ----
const editVisible = ref(false)
const editMode = ref('create')
const editId = ref(null)
const editRef = ref()
const editSaving = ref(false)
const editForm = reactive({ name: '', phone: '', email: '', remark: '' })
const editRules = {
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  phone: [
    {
      validator: (_r, v, cb) => (!v || /^1[3-9]\d{9}$/.test(v.trim()) ? cb() : cb(new Error('请输入 11 位手机号'))),
      trigger: 'blur',
    },
  ],
}

function openCreate() {
  editMode.value = 'create'
  editId.value = null
  Object.assign(editForm, { name: '', phone: '', email: '', remark: '' })
  editVisible.value = true
}

function openEdit(row) {
  editMode.value = 'edit'
  editId.value = row.id
  Object.assign(editForm, {
    name: row.name || '',
    phone: row.phone || '',
    email: row.email || '',
    remark: row.remark || '',
  })
  editVisible.value = true
}

async function saveCandidate() {
  await editRef.value.validate()
  editSaving.value = true
  try {
    const payload = {
      name: editForm.name.trim(),
      phone: editForm.phone.trim() || '',
      email: editForm.email.trim() || '',
      remark: editForm.remark || null,
    }
    const saved =
      editMode.value === 'create'
        ? await candidateApi.create(payload)
        : await candidateApi.update(editId.value, payload)
    ElMessage.success(editMode.value === 'create' ? '候选人已创建' : '资料已更新')
    editVisible.value = false
    await load()
    if (detail.value && detail.value.id === editId.value) {
      detail.value = { ...detail.value, ...saved }
      await loadFiles(detail.value.id)
    }
    refreshStats?.()
  } finally {
    editSaving.value = false
  }
}

// ---- 详情抽屉 ----
const drawerVisible = ref(false)
const detail = ref(null)
const activeTab = ref('basic')
const apps = ref([])
const appsLoading = ref(false)
const files = ref([])
const filesLoading = ref(false)
const forms = ref([])
const formsLoading = ref(false)
const uploadCategory = ref('resume')
const uploading = ref(false)
const downloadingId = ref(null)

async function openDetail(row) {
  detail.value = row
  drawerVisible.value = true
  activeTab.value = 'basic'
  await Promise.all([loadApps(row.id), loadFiles(row.id), loadForms(row.id)])
}

async function loadApps(id) {
  appsLoading.value = true
  try {
    apps.value = await applicationApi.list({ can_id: id })
  } finally {
    appsLoading.value = false
  }
}

async function loadFiles(id) {
  filesLoading.value = true
  try {
    files.value = await candidateApi.files(id)
  } finally {
    filesLoading.value = false
  }
}

async function loadForms(id) {
  formsLoading.value = true
  try {
    forms.value = await candidateApi.forms(id)
  } finally {
    formsLoading.value = false
  }
}

async function doUpload(options) {
  uploading.value = true
  try {
    await candidateApi.uploadFile(detail.value.id, options.file, uploadCategory.value)
    ElMessage.success('文件已上传')
    await loadFiles(detail.value.id)
  } finally {
    uploading.value = false
  }
}

async function downloadFile(file) {
  downloadingId.value = file.id
  try {
    await candidateApi.downloadFile(file)
  } finally {
    downloadingId.value = null
  }
}

async function removeFile(file) {
  try {
    await ElMessageBox.confirm(`确定删除文件「${file.original_name}」？`, '删除文件', { type: 'warning' })
  } catch {
    return
  }
  await candidateApi.removeFile(file.id)
  ElMessage.success('已删除')
  await loadFiles(detail.value.id)
}

function gotoApplication(appId) {
  router.push({ name: 'application-detail', params: { id: appId } })
}

const CATEGORY_LABEL = { resume: '简历', certificate: '证书', portfolio: '作品', other: '其他' }
const FORM_STATUS = { draft: '草稿', submitted: '已提交' }

function sizeText(bytes) {
  if (!bytes && bytes !== 0) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function submissionAnswers(sub) {
  const out = {}
  for (const item of sub.items || []) out[item.field_key] = item.value
  return out
}

// ---- 模板字段缓存：渲染同一份字段结构 ----
const templateFieldsCache = new Map()

async function loadTemplateFields(templateId) {
  if (templateFieldsCache.has(templateId)) return templateFieldsCache.get(templateId)
  const detail = await formTemplateApi.detail(templateId)
  const fields = (detail.fields || []).filter((f) => f.is_active !== false)
  templateFieldsCache.set(templateId, fields)
  return fields
}

const formFieldsBySub = ref(new Map())

async function ensureFormFields(subs) {
  const next = new Map()
  for (const sub of subs) {
    try {
      next.set(sub.id, await loadTemplateFields(sub.template_id))
    } catch {
      next.set(sub.id, [])
    }
  }
  formFieldsBySub.value = next
}

watch(forms, (val) => {
  if (val && val.length) ensureFormFields(val)
  else formFieldsBySub.value = new Map()
}, { immediate: true })



// ---- 删除候选人 ----
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
    return
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
      <div class="head-actions">
        <span class="muted">共 {{ list.length }} 人</span>
        <el-button type="primary" @click="openCreate">
          <el-icon><Plus /></el-icon>&nbsp;新建候选人
        </el-button>
      </div>
    </div>

    <el-card shadow="never" class="filter-card">
      <el-form inline>
        <el-form-item label="姓名">
          <el-input
            v-model="filters.name"
            name="candidate-name"
            autocomplete="off"
            placeholder="姓名含…"
            clearable
            style="width: 130px"
            @keyup.enter="load"
          />
        </el-form-item>
        <el-form-item label="手机号">
          <el-input
            v-model="filters.phone"
            name="candidate-phone"
            autocomplete="off"
            placeholder="手机号含…"
            clearable
            style="width: 140px"
            @keyup.enter="load"
          />
        </el-form-item>
        <el-form-item label="账号">
          <el-select v-model="filters.has_account" placeholder="全部" clearable style="width: 130px">
            <el-option label="已开通账号" value="yes" />
            <el-option label="未开通 / 待补手机号" value="no" />
          </el-select>
        </el-form-item>
        <el-form-item label="投递情况">
          <el-select v-model="filters.has_application" placeholder="全部" clearable style="width: 130px">
            <el-option label="有投递记录" value="yes" />
            <el-option label="暂未投递" value="no" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="filters.remark"
            name="candidate-remark"
            autocomplete="off"
            placeholder="如 内推 / 二批"
            clearable
            style="width: 130px"
            @keyup.enter="load"
          />
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
      <el-table :data="list" v-loading="loading" border class="ats-vlist" empty-text="没有符合条件的候选人">
        <el-table-column label="姓名" min-width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <button type="button" class="link-btn" @click="openDetail(row)">{{ row.name }}</button>
          </template>
        </el-table-column>
        <el-table-column label="手机号" width="140">
          <template #default="{ row }">
            <span v-if="row.phone" class="ats-nums">{{ row.phone }}</span>
            <el-tag v-else type="warning" size="small" effect="plain">待补手机号</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="账号" width="110">
          <template #default="{ row }">
            <el-tag :type="row.has_account ? 'success' : 'info'" size="small" effect="plain">
              {{ row.has_account ? '已开通' : '未开通' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="140" show-overflow-tooltip>
          <template #default="{ row }">{{ row.remark || '—' }}</template>
        </el-table-column>
        <el-table-column label="名下投递" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="row.application_count > 0 ? 'primary' : 'info'" size="small" effect="plain">
              <span class="ats-nums">{{ row.application_count }}</span> 条
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="录入时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.create_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 候选人详情抽屉 -->
    <el-drawer v-model="drawerVisible" :title="detail ? `候选人：${detail.name}` : '候选人详情'" size="760px">
      <template v-if="detail">
        <el-tabs v-model="activeTab">
          <el-tab-pane label="基本信息" name="basic">
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item label="姓名">{{ detail.name }}</el-descriptions-item>
              <el-descriptions-item label="手机号">
                <span v-if="detail.phone" class="ats-nums">{{ detail.phone }}</span>
                <el-tag v-else type="warning" size="small" effect="plain">待补手机号</el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="邮箱">{{ detail.email || '—' }}</el-descriptions-item>
              <el-descriptions-item label="账号">
                <el-tag :type="detail.has_account ? 'success' : 'info'" size="small" effect="plain">
                  {{ detail.has_account ? '已开通（默认密码 admin）' : '未开通' }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item label="备注">{{ detail.remark || '—' }}</el-descriptions-item>
              <el-descriptions-item label="录入时间">{{ fmtTime(detail.create_time) }}</el-descriptions-item>
            </el-descriptions>
            <div class="drawer-actions">
              <el-button size="small" @click="openEdit(detail)">编辑资料</el-button>
            </div>
          </el-tab-pane>

          <el-tab-pane label="文件" name="files">
            <div class="tab-toolbar">
              <el-select v-model="uploadCategory" size="small" style="width: 120px" aria-label="文件分类">
                <el-option label="简历" value="resume" />
                <el-option label="证书" value="certificate" />
                <el-option label="作品" value="portfolio" />
                <el-option label="其他" value="other" />
              </el-select>
              <el-upload
                :show-file-list="false"
                :http-request="doUpload"
                accept=".pdf,.doc,.docx,.jpg,.jpeg,.png"
                :disabled="uploading"
              >
                <el-button size="small" type="primary" plain :loading="uploading">
                  <el-icon><Upload /></el-icon>&nbsp;上传文件
                </el-button>
              </el-upload>
              <span class="muted">PDF / DOC / DOCX / JPG / PNG，单文件 ≤10MB</span>
            </div>

            <el-table :data="files" v-loading="filesLoading" border size="small" empty-text="还没有上传文件">
              <el-table-column prop="original_name" label="文件名" min-width="190" show-overflow-tooltip />
              <el-table-column label="分类" width="80">
                <template #default="{ row }">{{ CATEGORY_LABEL[row.category] || row.category }}</template>
              </el-table-column>
              <el-table-column label="大小" width="90">
                <template #default="{ row }">{{ sizeText(row.size_bytes) }}</template>
              </el-table-column>
              <el-table-column label="版本" width="100">
                <template #default="{ row }">
                  <template v-if="row.category === 'resume'">
                    <el-tag v-if="row.is_current" size="small" type="success" effect="plain">当前简历</el-tag>
                    <span v-else class="muted">历史</span>
                  </template>
                  <span v-else class="muted">—</span>
                </template>
              </el-table-column>
              <el-table-column label="上传时间" width="145">
                <template #default="{ row }">{{ fmtTime(row.upload_time) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="110" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" :loading="downloadingId === row.id" @click="downloadFile(row)">
                    下载
                  </el-button>
                  <el-button link type="danger" @click="removeFile(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane label="表单答卷" name="forms">
            <div v-if="formsLoading" v-loading="true" class="form-loading" />
            <template v-else-if="forms.length">
              <div v-for="sub in forms" :key="sub.id" class="submission-card">
                <div class="submission-head">
                  <div>
                    <span class="submission-title">{{ sub.template_name }}</span>
                    <el-tag size="small" :type="sub.status === 'submitted' ? 'success' : 'info'" effect="plain">
                      {{ FORM_STATUS[sub.status] || sub.status }}
                    </el-tag>
                  </div>
                  <span class="muted">
                    v{{ sub.template_version }} · {{ fmtTime(sub.submit_time || sub.update_time) }}
                  </span>
                </div>
                <div class="submission-answers">
                  <PortalFormRenderer
                    :fields="formFieldsBySub.get(sub.id) || []"
                    :model-value="submissionAnswers(sub)"
                    :disabled="true"
                  />
                </div>
              </div>
            </template>
            <el-empty v-else description="还没有填写任何表单" :image-size="80" />
          </el-tab-pane>

          <el-tab-pane label="投递记录" name="apps">
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
          </el-tab-pane>
        </el-tabs>
      </template>

      <template #footer>
        <el-button @click="drawerVisible = false">关闭</el-button>
        <el-button v-if="detail" type="danger" plain @click="remove(detail)">删除该候选人</el-button>
      </template>
    </el-drawer>

    <!-- 新建 / 编辑候选人 -->
    <el-dialog
      v-model="editVisible"
      :title="editMode === 'create' ? '新建候选人' : '编辑候选人'"
      class="ats-dialog-narrow"
      destroy-on-close
    >
      <el-form ref="editRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="editForm.name" placeholder="候选人姓名" />
        </el-form-item>
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="editForm.phone" placeholder="11 位手机号；填了会自动开通候选人账号" maxlength="11" />
        </el-form-item>
        <el-form-item label="邮箱">
          <el-input v-model="editForm.email" placeholder="可不填" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="editForm.remark" placeholder="如 内推 / 猎头推荐" />
        </el-form-item>
      </el-form>
      <el-alert
        title="手机号是候选人登录账号，默认密码 admin"
        type="info"
        :closable="false"
        show-icon
        class="edit-tip"
      />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="editSaving" @click="saveCandidate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.head-actions {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-3);
}
.drawer-actions {
  margin-top: var(--ats-sp-4);
}
.tab-toolbar {
  display: flex;
  align-items: center;
  gap: var(--ats-sp-2);
  margin-bottom: var(--ats-sp-3);
  flex-wrap: wrap;
}
.form-loading {
  height: 120px;
}
.submission-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--ats-radius);
  padding: var(--ats-sp-3);
  margin-bottom: var(--ats-sp-3);
}
.submission-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--ats-sp-2);
  margin-bottom: var(--ats-sp-2);
}
.submission-title {
  font-weight: var(--ats-fw-medium);
  margin-right: var(--ats-sp-2);
}
.submission-answers {
  padding: var(--ats-sp-3) var(--ats-sp-4);
  background: var(--el-fill-color-lighter);
  border-radius: var(--ats-radius);
}
.edit-tip {
  margin-top: var(--ats-sp-2);
}

/* 表格里的姓名：打开抽屉是「动作」而不是「导航」，所以用 button 而不是 <a>。 */
.el-table .link-btn {
  padding: 0;
  background: none;
  font: inherit;
  color: var(--el-color-primary);
  border: 0;
  cursor: pointer;
}
.el-table .link-btn:hover {
  text-decoration: underline;
}
.el-table .link-btn:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
  border-radius: 2px;
}
</style>
