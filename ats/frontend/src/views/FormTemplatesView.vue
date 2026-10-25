<!--
  【表单模板管理】HR 定义「要问候选人什么」
    · 个人资料表：全局一份，候选人投递前必须提交
    · 岗位申请表：每个岗位一份，候选人投递后补填
  模板本身可改名/停用；字段改动会让版本 +1，历史答卷保留。
-->
<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import PortalFormRenderer from '../components/PortalFormRenderer.vue'
import { formTemplateApi, positionApi } from '../api'
import { fmtTime } from '../utils/format'

const list = ref([])
const positions = ref([])
const loading = ref(false)

const SCOPE_LABEL = { profile: '个人资料表', position: '岗位申请表', assessment: '职业底色图' }
const FIELD_TYPES = [
  { value: 'text', label: '单行文本' },
  { value: 'textarea', label: '多行文本' },
  { value: 'number', label: '数字' },
  { value: 'date', label: '日期' },
  { value: 'daterange', label: '日期区间' },
  { value: 'select', label: '下拉单选' },
  { value: 'radio', label: '单选按钮' },
  { value: 'checkbox', label: '多选' },
  { value: 'email', label: '邮箱' },
  { value: 'phone', label: '手机号' },
  { value: 'color', label: '红/蓝/绿底色选择' },
  { value: 'section', label: '分组标题（不收集答案）' },
]
const OPTION_TYPES = ['select', 'radio', 'checkbox', 'color']

// 常用模板：字段键、类型、选项都预置好，HR 套用后仍可增删改
const FORM_PRESETS = [
  {
    key: 'interview',
    name: '面试登记表',
    scope: 'position',
    description: '完整的面试登记表：个人信息、教育、工作、家庭与其他信息。',
    fields: [
      { field_key: 'section_personal', label: '个人信息', field_type: 'section', required: false, help_text: '请按身份证信息如实填写，带 * 为必填项。', sort_order: 1 },
      { field_key: 'name', label: '姓名', field_type: 'text', required: true, sort_order: 2 },
      { field_key: 'contact_phone', label: '联系电话', field_type: 'phone', required: true, placeholder: '保持畅通的手机号', sort_order: 3 },
      { field_key: 'id_card', label: '身份证号', field_type: 'text', required: false, max_length: 18, sort_order: 4 },
      { field_key: 'gender', label: '性别', field_type: 'select', required: false, options: ['男', '女'], sort_order: 5 },
      { field_key: 'ethnicity', label: '民族', field_type: 'text', required: false, sort_order: 6 },
      { field_key: 'birth_date', label: '出生日期', field_type: 'date', required: false, sort_order: 7 },
      { field_key: 'age', label: '年龄', field_type: 'number', required: false, sort_order: 8 },
      { field_key: 'blood_type', label: '血型', field_type: 'select', required: false, options: ['A', 'B', 'AB', 'O', '未知'], sort_order: 9 },
      { field_key: 'marital_status', label: '婚姻状况', field_type: 'select', required: false, options: ['未婚', '已婚', '离异', '其他'], sort_order: 10 },
      { field_key: 'native_place', label: '籍贯', field_type: 'text', required: false, sort_order: 11 },
      { field_key: 'height_cm', label: '身高（cm）', field_type: 'number', required: false, sort_order: 12 },
      { field_key: 'apply_position', label: '应聘岗位', field_type: 'text', required: false, sort_order: 13 },
      { field_key: 'health_status', label: '健康状况', field_type: 'select', required: false, options: ['良好', '一般', '需说明'], sort_order: 14 },
      { field_key: 'political_status', label: '政治面貌', field_type: 'select', required: false, options: ['群众', '共青团员', '中共党员', '其他'], sort_order: 15 },
      { field_key: 'current_address', label: '现居住地址', field_type: 'text', required: false, sort_order: 16 },

      { field_key: 'section_education', label: '教育经历（从高中写起）', field_type: 'section', required: false, help_text: '按时间从高到低填写；有多段经历可在「曾获奖励或突出成绩」里补充。', sort_order: 17 },
      { field_key: 'edu_school', label: '毕业学校', field_type: 'text', required: true, sort_order: 18 },
      { field_key: 'edu_period', label: '起止时间', field_type: 'daterange', required: true, sort_order: 19 },
      { field_key: 'edu_degree', label: '学历', field_type: 'select', required: true, options: ['高中', '大专', '本科', '硕士', '博士'], sort_order: 20 },
      { field_key: 'edu_major', label: '所学专业', field_type: 'text', required: false, sort_order: 21 },
      { field_key: 'edu_awards', label: '曾获奖励或突出成绩', field_type: 'textarea', required: false, sort_order: 22 },

      { field_key: 'section_work', label: '工作经历（由近及远）', field_type: 'section', required: false, help_text: '请填写最近一段工作；更早经历可另行补充。', sort_order: 23 },
      { field_key: 'work_company', label: '工作单位名称', field_type: 'text', required: true, sort_order: 24 },
      { field_key: 'work_period', label: '起止时间', field_type: 'daterange', required: true, sort_order: 25 },
      { field_key: 'work_department', label: '所在部门', field_type: 'text', required: false, sort_order: 26 },
      { field_key: 'work_title', label: '职务', field_type: 'text', required: false, sort_order: 27 },
      { field_key: 'work_reference', label: '证明人/职务/电话', field_type: 'text', required: false, sort_order: 28 },
      { field_key: 'work_reason', label: '离职原因', field_type: 'textarea', required: false, sort_order: 29 },

      { field_key: 'section_family', label: '家庭关系', field_type: 'section', required: false, sort_order: 30 },
      { field_key: 'family_relation', label: '称谓', field_type: 'text', required: false, sort_order: 31 },
      { field_key: 'family_name', label: '姓名', field_type: 'text', required: false, sort_order: 32 },
      { field_key: 'family_age', label: '年龄', field_type: 'number', required: false, sort_order: 33 },
      { field_key: 'family_company', label: '工作单位', field_type: 'text', required: false, sort_order: 34 },
      { field_key: 'family_title', label: '职务', field_type: 'text', required: false, sort_order: 35 },
      { field_key: 'family_contact', label: '联系方式', field_type: 'text', required: false, sort_order: 36 },

      { field_key: 'section_other', label: '其他', field_type: 'section', required: false, sort_order: 37 },
      { field_key: 'expected_salary', label: '期望薪资', field_type: 'text', required: false, sort_order: 38 },
      { field_key: 'onboard_date', label: '入职时间', field_type: 'date', required: false, sort_order: 39 },
      { field_key: 'specialties', label: '2个特长：', field_type: 'textarea', required: false, sort_order: 40 },
      { field_key: 'apply_channel', label: '你曾通过以下哪种方式应聘', field_type: 'text', required: false, sort_order: 41 },
      { field_key: 'referrer', label: '推荐人', field_type: 'text', required: false, sort_order: 42 },
    ],
  },
  {
    key: 'assessment',
    name: '职业底色图',
    scope: 'assessment',
    description: '用红/蓝/绿标出 15 项职业偏好，再补充你理想中的工作。',
    fields: [
      { field_key: 'section_intro', label: '涂色说明', field_type: 'section', required: false, help_text: '红色：对我非常重要，达不到会慎重考虑；蓝色：可以适当放宽，我也可以主动适应；绿色：我不会特别在意。请在每个格子里选择最符合你想法的颜色。', sort_order: 1 },
      { field_key: 'industry', label: '所属行业', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 2 },
      { field_key: 'major_match', label: '专业对口', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 3 },
      { field_key: 'skills', label: '工作技能', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 4 },
      { field_key: 'location', label: '工作地点', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 5 },
      { field_key: 'team_atmosphere', label: '团队氛围', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 6 },
      { field_key: 'communication', label: '沟通比重', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 7 },
      { field_key: 'overtime', label: '加班强度', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 8 },
      { field_key: 'free_choice', label: '自由选择', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 9 },
      { field_key: 'work_content', label: '工作内容', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 10 },
      { field_key: 'leadership', label: '领导性格', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 11 },
      { field_key: 'company_growth', label: '公司发展', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 12 },
      { field_key: 'team_size', label: '团队规模', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 13 },
      { field_key: 'personal_growth', label: '个人发展', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 14 },
      { field_key: 'living_cost', label: '生活成本', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 15 },
      { field_key: 'culture', label: '企业文化', field_type: 'color', required: false, options: ['红色', '蓝色', '绿色'], sort_order: 16 },
      { field_key: 'free_text', label: '自由填写', field_type: 'text', required: false, placeholder: '其他你在意的因素', sort_order: 17 },

      { field_key: 'section_voice', label: '我有话说', field_type: 'section', required: false, sort_order: 18 },
      { field_key: 'ideal_skills', label: '我理想中的工作，我希望它需要进一步掌握的工作技能是', field_type: 'textarea', required: false, sort_order: 19 },
      { field_key: 'ideal_team', label: '我理想中的工作，我希望它的团队氛围是', field_type: 'textarea', required: false, sort_order: 20 },
      { field_key: 'ideal_leader', label: '我理想中的工作，我希望我的领导性格是', field_type: 'textarea', required: false, sort_order: 21 },
      { field_key: 'communication_ratio', label: '我理想中的工作，我希望其中沟通的占比是___，原因是', field_type: 'select', required: false, options: ['高', '中', '低'], placeholder: '沟通占比', sort_order: 22 },
      { field_key: 'communication_reason', label: '请填写原因', field_type: 'textarea', required: false, placeholder: '请填写原因', sort_order: 23 },
      { field_key: 'salary_expectation', label: '我希望得到的薪资待遇以及每年加薪的幅度是', field_type: 'textarea', required: false, sort_order: 24 },
      { field_key: 'additional_hopes', label: '此外，我还希望它是', field_type: 'textarea', required: false, sort_order: 25 },
    ],
  },
]

async function load() {
  loading.value = true
  try {
    const [templates, pos] = await Promise.all([formTemplateApi.list(), positionApi.list(true)])
    list.value = templates
    positions.value = pos
  } finally {
    loading.value = false
  }
}
onMounted(load)

// ---- 模板信息 ----
const metaVisible = ref(false)
const metaMode = ref('create')
const metaRef = ref()
const metaSaving = ref(false)
const metaForm = reactive({ name: '', scope: 'profile', position_id: null, description: '' })
const presetFields = ref([])
const metaRules = {
  name: [{ required: true, message: '请输入模板名', trigger: 'blur' }],
  scope: [{ required: true, message: '请选择用途', trigger: 'change' }],
}

function openCreate() {
  metaMode.value = 'create'
  presetFields.value = []
  // 用途不再让 HR 选：空白新建默认就是某岗位的申请表；个人资料表/职业底色图走常用模板套用
  Object.assign(metaForm, { name: '', scope: 'position', position_id: null, description: '' })
  metaVisible.value = true
}

function openPreset(preset) {
  if (['profile', 'assessment'].includes(preset.scope) && list.value.some((t) => t.scope === preset.scope && t.is_active)) {
    ElMessage.warning(`已有启用中的${SCOPE_LABEL[preset.scope]}，请先停用旧模板再套用`)
    return
  }
  metaMode.value = 'create'
  presetFields.value = preset.fields.map((f) => ({ ...f, options: f.options ? [...f.options] : null }))
  Object.assign(metaForm, {
    name: preset.name,
    scope: preset.scope,
    position_id: null,
    description: preset.description,
  })
  metaVisible.value = true
}

function openEdit(row) {
  metaMode.value = 'edit'
  presetFields.value = []
  Object.assign(metaForm, {
    name: row.name,
    scope: row.scope,
    position_id: row.position_id,
    description: row.description || '',
    id: row.id,
  })
  metaVisible.value = true
}

async function saveMeta() {
  await metaRef.value.validate()
  metaSaving.value = true
  try {
    if (metaMode.value === 'create') {
      const created = await formTemplateApi.create({
        name: metaForm.name.trim(),
        scope: metaForm.scope,
        position_id: metaForm.scope === 'position' ? metaForm.position_id : null,
        description: metaForm.description || null,
        fields: presetFields.value,
      })
      metaVisible.value = false
      await load()
      if (presetFields.value.length) {
        ElMessage.success(`已套用「${metaForm.name}」模板`)
      } else {
        ElMessage.success('模板已创建，接着添加字段')
        await openFields(created)
      }
    } else {
      await formTemplateApi.update(metaForm.id, {
        name: metaForm.name.trim(),
        description: metaForm.description || null,
      })
      ElMessage.success('模板已更新')
      metaVisible.value = false
      await load()
    }
  } finally {
    metaSaving.value = false
  }
}

// ---- 模板预览（候选人视角，只读）----
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewTemplate = ref(null)

function previewFromPreset(preset) {
  previewTemplate.value = { name: preset.name, description: preset.description, fields: preset.fields }
  previewVisible.value = true
}

async function openPreview(row) {
  previewVisible.value = true
  previewLoading.value = true
  previewTemplate.value = null
  try {
    previewTemplate.value = await formTemplateApi.detail(row.id)
  } finally {
    previewLoading.value = false
  }
}

async function deactivate(row) {
  try {
    await ElMessageBox.confirm(
      `停用「${row.name}」后，候选人将不再看到这张表；历史答卷保留。确定停用？`,
      '停用模板',
      { type: 'warning' },
    )
  } catch {
    return
  }
  await formTemplateApi.deactivate(row.id)
  ElMessage.success('已停用')
  await load()
}

async function activate(row) {
  try {
    await formTemplateApi.update(row.id, { is_active: true })
    ElMessage.success('已启用')
    await load()
  } catch {
    /* 同范围已有启用中的模板时，后端会提示 */
  }
}

async function purge(row) {
  try {
    await ElMessageBox.confirm(
      `彻底删除「${row.name}」？模板及其字段会从系统里移除，且不可恢复。只有没有任何答卷的停用模板才能删除。`,
      '删除模板',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await formTemplateApi.purge(row.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    if (e.response?.status === 409) ElMessage.warning(e.response.data?.detail || '该模板已有答卷，不能删除')
  }
}

// ---- 字段编辑 ----
const fieldsVisible = ref(false)
const fieldsSaving = ref(false)
const fieldsTemplate = ref(null)
const fieldRows = ref([])

function rowFromField(f) {
  return {
    field_key: f.field_key,
    label: f.label,
    field_type: f.field_type,
    required: !!f.required,
    optionsText: (f.options || []).join(' | '),
    placeholder: f.placeholder || '',
    help_text: f.help_text || '',
    max_length: f.max_length || null,
    is_active: f.is_active !== false,
  }
}

async function openFields(row) {
  const detail = await formTemplateApi.detail(row.id)
  fieldsTemplate.value = detail
  fieldRows.value = detail.fields.map(rowFromField)
  fieldsVisible.value = true
}

function addField() {
  fieldRows.value.push({
    field_key: '',
    label: '',
    field_type: 'text',
    required: false,
    optionsText: '',
    placeholder: '',
    help_text: '',
    max_length: null,
    is_active: true,
  })
}

function removeField(index) {
  fieldRows.value.splice(index, 1)
}

function moveField(index, delta) {
  const next = index + delta
  if (next < 0 || next >= fieldRows.value.length) return
  const rows = fieldRows.value
  ;[rows[index], rows[next]] = [rows[next], rows[index]]
}

function parseOptions(text) {
  return String(text || '')
    .split(/[|,，\n]/)
    .map((x) => x.trim())
    .filter(Boolean)
}

async function saveFields() {
  const fields = fieldRows.value.map((r, i) => ({
    field_key: r.field_key.trim(),
    label: r.label.trim(),
    field_type: r.field_type,
    required: r.field_type === 'section' ? false : !!r.required,
    options: OPTION_TYPES.includes(r.field_type) ? parseOptions(r.optionsText) : null,
    placeholder: r.placeholder || null,
    help_text: r.help_text || null,
    max_length: r.max_length ? Number(r.max_length) : null,
    sort_order: i + 1,
    is_active: r.is_active !== false,
  }))
  fieldsSaving.value = true
  try {
    await formTemplateApi.saveFields(fieldsTemplate.value.id, fields)
    ElMessage.success('字段已保存，版本已更新')
    fieldsVisible.value = false
    await load()
  } finally {
    fieldsSaving.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>表单模板</h2>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>&nbsp;新建模板
      </el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      show-icon
      title="个人资料表、职业底色图全局各只能有一个启用中；每个岗位也只能有一个启用中的申请表"
      description="字段改动会让版本 +1；删除字段只是停用，历史答卷仍然保留。"
      class="tip"
    />

    <section class="preset-section">
      <div class="preset-head">
        <div>
          <h3>常用模板</h3>
          <p>一键套用，字段已经填好，创建后仍可继续增删改。</p>
        </div>
      </div>
      <div class="preset-grid">
        <button
          v-for="preset in FORM_PRESETS"
          :key="preset.key"
          type="button"
          class="preset-card"
          @click="openPreset(preset)"
        >
          <div class="preset-top">
            <span class="preset-icon"><el-icon><Document /></el-icon></span>
            <span class="preset-name">{{ preset.name }}</span>
            <el-tag size="small" effect="plain">{{ SCOPE_LABEL[preset.scope] }}</el-tag>
          </div>
          <p class="preset-desc">{{ preset.description }}</p>
          <div class="preset-foot">
            <span>{{ preset.fields.length }} 个字段</span>
            <span class="preset-foot-actions">
              <span class="preset-preview" @click.stop="previewFromPreset(preset)">预览</span>
              <span class="preset-action">套用 <el-icon><ArrowRight /></el-icon></span>
            </span>
          </div>
        </button>
      </div>
    </section>

    <section class="panel">
      <el-table :data="list" v-loading="loading" border empty-text="还没有表单模板">
        <el-table-column prop="name" label="模板名" min-width="180" show-overflow-tooltip />
        <el-table-column label="用途" width="110">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ SCOPE_LABEL[row.scope] || row.scope }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="岗位" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <span v-if="row.scope === 'position' && !row.position_id" class="muted">全部岗位（通用）</span>
            <template v-else>{{ row.position_name || '—' }}</template>
          </template>
        </el-table-column>
        <el-table-column label="版本" width="70" align="center">
          <template #default="{ row }"><span class="ats-nums">v{{ row.version }}</span></template>
        </el-table-column>
        <el-table-column label="字段数" width="80" align="center">
          <template #default="{ row }"><span class="ats-nums">{{ row.field_count }}</span></template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small" effect="plain">
              {{ row.is_active ? '启用中' : '已停用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="更新时间" width="150">
          <template #default="{ row }">{{ fmtTime(row.update_time) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openPreview(row)">预览</el-button>
            <el-button link type="primary" @click="openFields(row)">字段</el-button>
            <el-button link @click="openEdit(row)">信息</el-button>
            <el-button v-if="row.is_active" link type="danger" @click="deactivate(row)">停用</el-button>
            <el-button v-else link type="success" @click="activate(row)">启用</el-button>
            <el-button v-if="!row.is_active" link type="danger" @click="purge(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 模板预览：弹窗本体即毛玻璃，能透出后面页面的轮廓；只读展示 -->
    <el-dialog
      v-model="previewVisible"
      :title="previewTemplate ? `预览：${previewTemplate.name}` : '预览'"
      class="preview-dialog"
      modal-class="preview-overlay"
      append-to-body
      destroy-on-close
    >
      <div v-loading="previewLoading" class="preview-body">
        <template v-if="previewTemplate">
          <p v-if="previewTemplate.description" class="preview-desc">{{ previewTemplate.description }}</p>
          <PortalFormRenderer :fields="previewTemplate.fields || []" disabled />
          <p class="preview-note muted">以上是候选人看到的填写样式，此处为只读预览。</p>
        </template>
      </div>
    </el-dialog>

    <!-- 模板信息 -->
    <el-dialog
      v-model="metaVisible"
      :title="metaMode === 'create' ? '新建表单模板' : '编辑模板信息'"
      class="ats-dialog-narrow"
      destroy-on-close
    >
      <el-form ref="metaRef" :model="metaForm" :rules="metaRules" label-width="90px">
        <el-form-item label="模板名" prop="name">
          <el-input v-model="metaForm.name" placeholder="如 候选人资料表 / Java 岗申请表" />
        </el-form-item>
        <el-form-item v-if="metaForm.scope === 'position'" label="岗位">
          <el-select v-model="metaForm.position_id" filterable clearable placeholder="不选 = 全部岗位通用" style="width: 100%">
            <el-option v-for="p in positions" :key="p.id" :label="p.position_name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="metaForm.description" type="textarea" :rows="2" placeholder="展示给候选人的一句话说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="metaVisible = false">取消</el-button>
        <el-button type="primary" :loading="metaSaving" @click="saveMeta">保存</el-button>
      </template>
    </el-dialog>

    <!-- 字段编辑 -->
    <el-dialog
      v-model="fieldsVisible"
      :title="fieldsTemplate ? `字段：${fieldsTemplate.name}` : '字段'"
      class="ats-dialog-full"
      destroy-on-close
    >
      <el-alert
        type="info"
        :closable="false"
        show-icon
        title="字段键只能用英文字母开头（字母/数字/下划线），同一模板内不能重复"
        description="选项用 | 或逗号分隔；删除的行在保存后会变成「停用」，历史答案保留。"
        class="tip"
      />
      <el-table :data="fieldRows" border size="small" class="field-table">
        <el-table-column label="#" width="64">
          <template #default="{ $index }">
            <div class="sort-btns">
              <el-button link size="small" :disabled="$index === 0" @click="moveField($index, -1)">↑</el-button>
              <el-button link size="small" :disabled="$index === fieldRows.length - 1" @click="moveField($index, 1)">↓</el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="字段键" width="140">
          <template #default="{ row }">
            <el-input v-model="row.field_key" size="small" placeholder="如 education" />
          </template>
        </el-table-column>
        <el-table-column label="显示名" width="150">
          <template #default="{ row }">
            <el-input v-model="row.label" size="small" placeholder="如 最高学历" />
          </template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <el-select v-model="row.field_type" size="small">
              <el-option v-for="t in FIELD_TYPES" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="必填" width="70" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.required" size="small" :disabled="row.field_type === 'section'" />
          </template>
        </el-table-column>
        <el-table-column label="选项（| 分隔）" min-width="200">
          <template #default="{ row }">
            <el-input
              v-if="['select', 'radio', 'checkbox', 'color'].includes(row.field_type)"
              v-model="row.optionsText"
              size="small"
              placeholder="本科 | 硕士 | 博士"
            />
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="最大长度" width="100">
          <template #default="{ row }">
            <el-input v-model="row.max_length" size="small" placeholder="不限" />
          </template>
        </el-table-column>
        <el-table-column label="启用" width="70" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.is_active" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="70" fixed="right">
          <template #default="{ $index }">
            <el-button link type="danger" @click="removeField($index)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-button class="add-field" plain @click="addField">
        <el-icon><Plus /></el-icon>&nbsp;添加字段
      </el-button>
      <template #footer>
        <el-button @click="fieldsVisible = false">取消</el-button>
        <el-button type="primary" :loading="fieldsSaving" @click="saveFields">保存字段</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.tip {
  margin-bottom: var(--ats-sp-3);
}
.preset-section {
  margin-bottom: var(--ats-sp-4);
}
.preset-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-bottom: var(--ats-sp-3);
}
.preset-head h3 {
  margin: 0;
  font-size: var(--ats-fs-card);
  font-weight: var(--ats-fw-medium);
}
.preset-head p {
  margin: 4px 0 0;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
}
.preset-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--ats-sp-3);
}
.preset-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: var(--ats-sp-4);
  text-align: left;
  font: inherit;
  color: inherit;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.preset-card:hover {
  border-color: var(--el-color-primary-light-5);
  box-shadow: 0 8px 24px rgb(10 40 36 / 8%);
  transform: translateY(-1px);
}
.preset-card:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 1px;
}
.preset-top {
  display: flex;
  align-items: center;
  gap: 8px;
}
.preset-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border-radius: 8px;
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  flex: none;
}
.preset-name {
  font-size: var(--ats-fs-body);
  font-weight: var(--ats-fw-medium);
}
.preset-desc {
  margin: 0;
  min-height: 38px;
  font-size: var(--ats-fs-label);
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
.preset-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-placeholder);
}
.preset-action {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--el-color-primary);
}
.preset-foot-actions {
  display: inline-flex;
  align-items: center;
  gap: 12px;
}
.preset-preview {
  color: var(--el-text-color-secondary);
  cursor: pointer;
}
.preset-preview:hover {
  color: var(--el-color-primary);
}
/* 预览弹窗：本体就是毛玻璃——半透明底 + backdrop-filter，
   能看到弹窗后面页面的模糊轮廓；面板大圆角。
   注意：class 会挂在 .el-dialog / .el-overlay 元素「自身」上，
   必须用复合选择器，写成后代选择器匹配不到。 */
:global(.el-overlay.preview-overlay) {
  /* 遮罩调淡，后面页面透得更清楚，玻璃感才出来 */
  background: rgb(0 0 0 / 12%) !important;
}
:global(.el-dialog.preview-dialog) {
  /* 不用全宽：留出四周的页面，玻璃才有东西可透，圆角也看得见 */
  width: min(880px, calc(100vw - 64px));
  background: color-mix(in srgb, var(--el-bg-color) 32%, transparent);
  backdrop-filter: blur(40px) saturate(180%);
  -webkit-backdrop-filter: blur(40px) saturate(180%);
  border: 1px solid color-mix(in srgb, var(--el-bg-color) 45%, transparent);
  border-radius: 36px;
  box-shadow: 0 24px 80px rgb(10 40 36 / 18%);
  overflow: hidden;
}
:global(.el-dialog.preview-dialog .el-dialog__header) {
  margin-right: 0;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.preview-desc {
  margin: 0 0 var(--ats-sp-3);
  font-size: var(--ats-fs-note);
  color: var(--el-text-color-secondary);
}
.preview-note {
  margin: var(--ats-sp-3) 0 0;
  text-align: center;
}
.field-table {
  margin-top: var(--ats-sp-2);
}
.sort-btns {
  display: flex;
  gap: 0;
}
.add-field {
  margin-top: var(--ats-sp-3);
  width: 100%;
  border-style: dashed;
}
@media (max-width: 760px) {
  .preset-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
