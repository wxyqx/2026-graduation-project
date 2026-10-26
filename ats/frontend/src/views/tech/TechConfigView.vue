<script setup>
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { techConfigApi } from '../../api/tech'

const list = ref([])
const loading = ref(false)
const helpVisible = ref(false)

// ---- 隐私政策与 AI 筛选告知（候选人端投递/填表/回传前的同意依据）----
const privacy = reactive({ version: '', text: '' })
const privacySaving = ref(false)

async function loadPrivacy() {
  const d = await techConfigApi.getPrivacy()
  privacy.version = d.version
  privacy.text = d.text
}

async function savePrivacy() {
  privacySaving.value = true
  try {
    const d = await techConfigApi.savePrivacy(privacy.text)
    privacy.version = d.version
    ElMessage.success('隐私政策已保存，新同意记录将引用新版本')
  } finally {
    privacySaving.value = false
  }
}

// ---- 淘汰申诉联系方式（通知模板 {申诉联系方式} 占位符）----
const appeal = reactive({ text: '' })
const appealSaving = ref(false)

async function loadAppeal() {
  const d = await techConfigApi.getAppeal()
  appeal.text = d.text
}

async function saveAppeal() {
  appealSaving.value = true
  try {
    const d = await techConfigApi.saveAppeal(appeal.text)
    appeal.text = d.text
    ElMessage.success('申诉联系方式已保存')
  } finally {
    appealSaving.value = false
  }
}

async function load() {
  loading.value = true
  try {
    list.value = await techConfigApi.list()
  } finally {
    loading.value = false
  }
}
onMounted(() => {
  load()
  loadPrivacy()
  loadAppeal()
})

// ---- SMTP 邮件配置（通知的邮件渠道）----
const smtp = reactive({
  enabled: false, host: '', port: 465, use_ssl: true,
  username: '', password: '', has_password: false,
  sender_name: 'ATS 招聘系统', site_url: 'http://127.0.0.1:5173/portal/login',
})
const smtpSaving = ref(false)
const smtpTo = ref('')
const smtpTesting = ref(false)

async function loadSmtp() {
  const d = await techEmailApi.get()
  Object.assign(smtp, d)  // password 恒为空（后端不回显）
}

async function saveSmtp() {
  if (smtp.enabled && (!smtp.host || !smtp.username)) {
    ElMessage.warning('启用邮件渠道需要填 SMTP 服务器和发件邮箱')
    return
  }
  smtpSaving.value = true
  try {
    const d = await techEmailApi.save({ ...smtp })
    Object.assign(smtp, d)
    ElMessage.success('SMTP 配置已保存')
  } finally {
    smtpSaving.value = false
  }
}

async function testSmtp() {
  if (!smtpTo.value) {
    ElMessage.warning('先填收件邮箱（配置会先保存）')
    return
  }
  smtpTesting.value = true
  try {
    await saveSmtp()
    await techEmailApi.test(smtpTo.value)
    ElMessage.success('测试邮件已发出，请查收（没收到看看垃圾箱）')
  } finally {
    smtpTesting.value = false
  }
}

// ---- 提示词 ----
const promptRules = ref('')
const promptDefault = ref('')
const promptFormat = ref('')
const promptSaved = ref(false)
const savingPrompt = ref(false)

async function loadPrompt() {
  const d = await techConfigApi.getPrompt()
  promptRules.value = d.rules
  promptDefault.value = d.default_rules
  promptFormat.value = d.format_rules
  promptSaved.value = d.is_custom
}
onMounted(loadPrompt)
onMounted(loadSmtp)

async function savePrompt() {
  savingPrompt.value = true
  try {
    const d = await techConfigApi.savePrompt(promptRules.value)
    promptRules.value = d.rules
    promptSaved.value = d.is_custom
    ElMessage.success('提示词已保存，AI 录入 / 候选人投递立刻生效')
  } finally {
    savingPrompt.value = false
  }
}

async function clearPrompt() {
  savingPrompt.value = true
  try {
    const d = await techConfigApi.savePrompt('')
    promptRules.value = d.rules
    promptSaved.value = d.is_custom
    ElMessage.success('已恢复系统默认规则')
  } finally {
    savingPrompt.value = false
  }
}

// ---- 配置弹窗 ----
const dialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref()
const form = reactive({ name: '', base_url: '', api_key: '', model: '', is_enabled: false })
const rules = {
  name: [{ required: true, message: '请输入配置名称', trigger: 'blur' }],
  base_url: [
    { required: true, message: '请输入接口地址', trigger: 'blur' },
    { type: 'url', message: '地址格式不对（要 http:// 或 https:// 开头）', trigger: 'blur' },
  ],
  api_key: [{ required: true, message: '请输入密钥', trigger: 'blur' }],
  model: [{ required: true, message: '请输入模型名', trigger: 'blur' }],
}
const saving = ref(false)

function openCreate() {
  editingId.value = null
  Object.assign(form, { name: '', base_url: '', api_key: '', model: '', is_enabled: false })
  dialogVisible.value = true
}
function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    name: row.name,
    base_url: row.base_url,
    api_key: row.api_key,
    model: row.model,
    is_enabled: row.is_enabled,
  })
  dialogVisible.value = true
}

async function save() {
  await formRef.value.validate()
  saving.value = true
  try {
    if (editingId.value === null) {
      await techConfigApi.create({ ...form })
      ElMessage.success('配置已添加')
    } else {
      await techConfigApi.update(editingId.value, { ...form })
      ElMessage.success('配置已更新')
    }
    dialogVisible.value = false
    await load()
  } finally {
    saving.value = false
  }
}

async function toggle(row) {
  if (row.is_enabled) await techConfigApi.disable(row.id)
  else await techConfigApi.enable(row.id)
  ElMessage.success(row.is_enabled ? '已停用' : '已启用')
  await load()
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除配置「${row.name}」？`, '删除配置', { type: 'warning' })
  } catch {
    return
  }
  await techConfigApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}
</script>

<template>
  <div>
    <div class="page-header">
      <h2>系统配置</h2>
      <el-button type="primary" @click="openCreate">
        <el-icon><Plus /></el-icon>&nbsp;新建 AI 配置
      </el-button>
    </div>

    <!-- 隐私政策与 AI 筛选告知：候选人端投递/填表/回传前必须同意（PIPL 告知-同意） -->
    <section class="ats-panel" style="margin-bottom: 16px">
      <div class="card-header">
        <span class="ats-panel-title" style="margin: 0">隐私政策与 AI 筛选告知</span>
        <span class="muted">当前版本 {{ privacy.version || '—' }}</span>
      </div>
      <p class="muted" style="margin: 0 0 8px">
        候选人首次登录会弹窗展示本文案，勾选同意后才能投递、填表、回传；保存即生成新版本号，已同意过的人不用重签。
      </p>
      <el-input v-model="privacy.text" type="textarea" :autosize="{ minRows: 8, maxRows: 16 }" />
      <div style="margin-top: 10px">
        <el-button type="primary" :loading="privacySaving" @click="savePrivacy">保存隐私政策</el-button>
      </div>
    </section>

    <!-- 淘汰申诉联系方式：{申诉联系方式} 占位符取值 -->
    <section class="ats-panel" style="margin-bottom: 16px">
      <div class="card-header">
        <span class="ats-panel-title" style="margin: 0">淘汰申诉联系方式</span>
      </div>
      <p class="muted" style="margin: 0 0 8px">
        填入「系统设置 → 通过/淘汰通知模板」里的 {申诉联系方式} 占位符，随淘汰通知与登录拦截信息一起发给候选人；留空恢复默认文案。
      </p>
      <el-input v-model="appeal.text" type="textarea" :autosize="{ minRows: 2, maxRows: 4 }" maxlength="500" />
      <div style="margin-top: 10px">
        <el-button type="primary" :loading="appealSaving" @click="saveAppeal">保存申诉联系方式</el-button>
      </div>
    </section>

    <section class="ats-panel">
      <div class="card-header">
        <span class="ats-panel-title" style="margin: 0">AI 筛选 API</span>
        <el-button link type="primary" size="small" @click="helpVisible = !helpVisible">
          {{ helpVisible ? '收起帮助' : '哪里申请密钥？' }}
        </el-button>
      </div>

      <el-collapse-transition>
        <div v-if="helpVisible" class="help">
          <p>支持所有「OpenAI 兼容」服务，任选一家注册并创建 API Key：</p>
          <table>
            <tr><th>服务</th><th>接口地址（base_url）</th><th>模型名示例</th></tr>
            <tr><td>智谱 GLM</td><td>https://open.bigmodel.cn/api/paas/v4</td><td>glm-4-flash（免费）</td></tr>
            <tr><td>通义千问</td><td>https://dashscope.aliyuncs.com/compatible-mode/v1</td><td>qwen-turbo</td></tr>
            <tr><td>DeepSeek</td><td>https://api.deepseek.com/v1</td><td>deepseek-chat</td></tr>
          </table>
          <p class="muted">base_url 填到 /v4 或 /v1 即可，系统自动补 /chat/completions。可同时启用多个，AI 筛选时轮询使用。</p>
        </div>
      </el-collapse-transition>

      <el-table :data="list" v-loading="loading" empty-text="还没有 AI 配置">
        <el-table-column prop="name" label="名称" width="160" />
        <el-table-column prop="base_url" label="接口地址" min-width="240" show-overflow-tooltip />
        <el-table-column prop="model" label="模型" width="160" />
        <el-table-column label="启用" width="100" align="center">
          <template #default="{ row }">
            <el-switch :model-value="row.is_enabled" :aria-label="`启用配置：${row.name}`" @change="toggle(row)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="ats-panel">
      <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px">
        <span class="ats-panel-title" style="margin: 0">SMTP 邮件配置</span>
        <el-switch v-model="smtp.enabled" active-text="启用邮件渠道" />
      </div>
      <p class="muted" style="margin-top: 0">
        启用后，HR 发送通知（通过 / 入职 / 淘汰）且候选人档案里有邮箱时，系统异步补发一封同样内容的邮件。
        发送失败不影响站内通知。个人邮箱（QQ / 163）用「授权码」，不是登录密码。
      </p>
      <el-form label-width="110px" :disabled="!smtp.enabled" style="max-width: 560px">
        <el-form-item label="SMTP 服务器">
          <el-input v-model="smtp.host" placeholder="如 smtp.qq.com" />
        </el-form-item>
        <el-form-item label="端口">
          <el-radio-group v-model="smtp.use_ssl">
            <el-radio :value="true">465（SSL）</el-radio>
            <el-radio :value="false">587（STARTTLS）</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="发件邮箱">
          <el-input v-model="smtp.username" placeholder="如 ats@example.com" />
        </el-form-item>
        <el-form-item label="授权码">
          <el-input
            v-model="smtp.password"
            type="password"
            show-password
            :placeholder="smtp.has_password ? '已保存（填新值即覆盖）' : '邮箱服务商的 SMTP 授权码'"
          />
        </el-form-item>
        <el-form-item label="发件人显示名">
          <el-input v-model="smtp.sender_name" />
        </el-form-item>
        <el-form-item label="候选人端地址">
          <el-input v-model="smtp.site_url" placeholder="邮件末尾附的登录链接；穿透/部署后改成公网地址" />
        </el-form-item>
        <el-form-item label="测试">
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input v-model="smtpTo" placeholder="收件邮箱" />
            <el-button :loading="smtpTesting" @click="testSmtp">保存并发送测试邮件</el-button>
          </div>
        </el-form-item>
      </el-form>
      <div style="margin-top: 8px">
        <el-button type="primary" :loading="smtpSaving" @click="saveSmtp">保存 SMTP 配置</el-button>
      </div>
    </section>

    <section class="ats-panel prompt-panel">
      <div class="card-header">
        <span class="ats-panel-title" style="margin: 0">AI 筛选提示词</span>
        <el-tag v-if="promptSaved" type="success" size="small">已自定义</el-tag>
        <el-tag v-else type="info" size="small">系统默认</el-tag>
      </div>
      <p class="muted" style="margin-top: 0">
        这里写的是<b>筛选规则</b>——AI 判断简历通过与否时遵循的标准（岗位要求之外的额外标准）。
        它会用在 HR 的「AI 录入简历」和候选人自主投递里。
      </p>
      <el-alert
        type="warning"
        show-icon
        :closable="false"
        style="margin-bottom: 10px"
        title="合规提示：筛选规则不得包含年龄、性别、民族、院校出身等歧视性条件；AI 初筛结果仅作参考，录用决定必须由人工复核作出（AI 淘汰一律转人工确认）。"
      />
      <el-input
        v-model="promptRules"
        type="textarea"
        aria-label="AI 筛选提示词"
        :rows="7"
        maxlength="8000"
        show-word-limit
        placeholder="例：&#10;1. 只要 985/211 院校毕业；&#10;2. 必须有医疗行业项目经验；&#10;3. 不接收外包背景。"
      />
      <div class="prompt-actions">
        <el-button type="primary" :loading="savingPrompt" @click="savePrompt">保存</el-button>
        <el-button @click="promptRules = promptDefault">恢复默认</el-button>
        <el-button :loading="savingPrompt" @click="clearPrompt">清除自定义</el-button>
      </div>
      <el-collapse class="format-collapse">
        <el-collapse-item title="系统锁定的回答格式（只读，不可修改）" name="format">
          <pre class="format">{{ promptFormat }}</pre>
        </el-collapse-item>
      </el-collapse>
    </section>

    <el-dialog v-model="dialogVisible" :title="editingId === null ? '新建 AI 配置' : '编辑 AI 配置'" class="ats-dialog-narrow" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如 GLM 免费版" />
        </el-form-item>
        <el-form-item label="接口地址" prop="base_url">
          <el-input v-model="form.base_url" placeholder="https://open.bigmodel.cn/api/paas/v4" />
        </el-form-item>
        <el-form-item label="密钥" prop="api_key">
          <el-input v-model="form.api_key" placeholder="API Key" show-password />
        </el-form-item>
        <el-form-item label="模型" prop="model">
          <el-input v-model="form.model" placeholder="glm-4-flash" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.prompt-panel {
  margin-top: var(--ats-sp-4);
}
.prompt-actions {
  margin-top: var(--ats-sp-3);
  display: flex;
  gap: var(--ats-sp-2);
}
.help {
  padding: var(--ats-sp-3);
  background: var(--el-fill-color-light);
  border-radius: var(--ats-radius);
  margin-bottom: var(--ats-sp-3);
  font-size: var(--ats-fs-note);
}
.help table {
  border-collapse: collapse;
  margin: 8px 0;
}
.help th,
.help td {
  border: 1px solid var(--el-border-color-light);
  padding: 4px 10px;
  text-align: left;
}
.format-collapse {
  margin-top: var(--ats-sp-4);
}
.format {
  margin: 0;
  white-space: pre-wrap;
  font-size: var(--ats-fs-label);
  color: var(--el-text-color-secondary);
  line-height: 1.7;
}
</style>
