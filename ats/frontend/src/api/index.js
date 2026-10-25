/**
 * 【这个文件是干什么的？】
 * 把后端的每个接口包成一个函数，页面里调函数就行，不用记网址。按后端 routers/ 的分组来分。
 * 每个函数返回的都是后端回的数据（http.js 已经帮我们取出 data 了）。
 */
import http from './http'

// ---- 认证 ----
export const authApi = {
  register: (username, password) => http.post('/auth/register', { username, password }, { silent: true }),
  login: (username, password) => http.post('/auth/login', { username, password }, { silent: true }),
  me: () => http.get('/auth/me'),
  // 修改个人信息（用户名 / 密码）。data 例：{username} 或 {username, current_password, new_password}
  // 后端会重新发一张 token，前端拿到后要替换本地登录状态
  updateProfile: (data) => http.put('/auth/profile', data),
  // 头像：上传即替换；获取返回 blob（404 = 未设置，前端显示首字占位）
  updateAvatar: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return http.put('/auth/avatar', fd)
  },
  avatarBlob: () => http.get('/auth/avatar', { responseType: 'blob', silent: true }),
}

// ---- 岗位 ----
export const positionApi = {
  // includeHidden=true 时连「暂不招」的岗位一起返回（岗位管理页用）；默认只返回在招的
  list: (includeHidden = false) => http.get('/positions', { params: includeHidden ? { include_hidden: true } : {} }),
  create: (data) => http.post('/positions', data),
  update: (id, data) => http.put(`/positions/${id}`, data),
  remove: (id) => http.delete(`/positions/${id}`),
}

// ---- 候选人 ----
export const candidateApi = {
  // 参数可以是字符串（当姓名搜索用）或对象（{name, remark, has_application, phone, has_account}）
  list: (query) => http.get('/candidates', { params: typeof query === 'string' ? (query ? { name: query } : {}) : (query || {}) }),
  detail: (id) => http.get(`/candidates/${id}`),
  create: (data) => http.post('/candidates', data),
  update: (id, data) => http.put(`/candidates/${id}`, data),
  remove: (id) => http.delete(`/candidates/${id}`), // 级联删除：连带删掉他名下的投递
  // 文件（HR 上传 / 候选人只读）
  files: (id) => http.get(`/candidates/${id}/files`),
  uploadFile: (id, file, category = 'resume', applicationId = null) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('category', category)
    if (applicationId) fd.append('application_id', String(applicationId))
    return http.post(`/candidates/${id}/files`, fd)
  },
  removeFile: (fileId) => http.delete(`/files/${fileId}`),
  // 发送 Offer 文件给候选人（重复发送幂等，保留首次发送时间）
  sendOfferFile: (fileId) => http.put(`/files/${fileId}/send`),
  // 预览用：拿原始 blob（下载是触发浏览器保存，这个给调用方自己处理）
  fileBlob: (fileId) => http.get(`/files/${fileId}/download`, { responseType: 'blob' }),

  async downloadFile(file) {
    const resp = await http.get(`/files/${file.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = file.original_name || 'file'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
  // 该候选人的全部表单答卷（个人资料表 + 各投递岗位表）
  forms: (id) => http.get(`/candidates/${id}/forms`),
}

// ---- 投递 ----
export const applicationApi = {
  list: (params) => http.get('/applications', { params }),
  create: (can_id, pos_id) => http.post('/applications', { can_id, pos_id }),
  detail: (id) => http.get(`/applications/${id}`),
  // fromStage 必须是当前阶段，result 是 pass / fail
  advance: (id, fromStage, result) => http.post(`/applications/${id}/advance`, { fromStage, result }),
  // toStage 不传 = 撤销上一步
  revert: (id, toStage) => http.post(`/applications/${id}/revert`, toStage ? { toStage } : {}),
  // 给某一关补写「结果原因」/「面试评价」（不改流程状态；空字符串 = 清空该项）
  saveStageNote: (id, stage, reason, evaluation) =>
    http.put(`/applications/${id}/stage-note`, { stage, reason, evaluation }),
  // ---- 通过通知（草稿 → 编辑 → 发送）----
  appNotices: (appId) => http.get(`/applications/${appId}/notices`),
  editAppNotice: (appId, noticeId, data) => http.put(`/applications/${appId}/notices/${noticeId}`, data),
  sendAppNotice: (appId, noticeId) => http.post(`/applications/${appId}/notices/${noticeId}/send`),
  discardAppNotice: (appId, noticeId) => http.delete(`/applications/${appId}/notices/${noticeId}`),
  forms: (id) => http.get(`/applications/${id}/forms`),
}

// ---- 表单模板（HR 配置）----
export const formTemplateApi = {
  list: (params) => http.get('/form-templates', { params }),
  detail: (id) => http.get(`/form-templates/${id}`),
  create: (data) => http.post('/form-templates', data),
  update: (id, data) => http.put(`/form-templates/${id}`, data),
  saveFields: (id, fields) => http.put(`/form-templates/${id}/fields`, { fields }),
  deactivate: (id) => http.delete(`/form-templates/${id}`),
  // 物理删除：仅限已停用且没有答卷的模板，有答卷时后端返回 409
  purge: (id) => http.delete(`/form-templates/${id}?purge=true`),
}

// ---- 统计 ----
export const statsApi = {
  overview: () => http.get('/stats/overview'),
  // 阶段 × 岗位 交叉汇总表；params 例：{range:'week'} 或 {range:'custom', start_date, end_date}
  matrix: (params) => http.get('/stats/matrix', { params }),
  // 进行中的候选人所处阶段清单
  inProgress: (params) => http.get('/stats/in-progress', { params }),
  // 交叉表某个格子里具体是哪些人
  matrixCell: (params) => http.get('/stats/matrix/cell', { params }),
}

// ---- 系统设置（阶段文案改写、候选人表单可见阶段）----
export const settingsApi = {
  // note 传空 = 恢复自动生成
  saveStageNote: (appId, note) => http.put('/settings/stage-note', { app_id: appId, note }),
  // 候选人在哪一关后能看到岗位申请表/职业底色图
  getPortalFormStage: () => http.get('/settings/portal-form-stage'),
  savePortalFormStage: (cfg) => http.put('/settings/portal-form-stage', cfg),
  // 通过通知模板（笔试/专业面/HR面/终面）
  getStageNotice: () => http.get('/settings/stage-notice'),
  saveStageNotice: (cfg) => http.put('/settings/stage-notice', cfg),
}

// ---- AI 录入简历 ----
// files: 浏览器 File 对象数组（PDF）；texts: 粘贴的纯文本数组
// extras: 各岗位的附加条件 {"岗位id": "文字"}；posId: 指定岗位编号（不传=AI 自动识别）
export async function uploadIntake(files, texts, extras = {}, posId = null) {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  for (const t of texts) fd.append('texts', t)
  if (extras && Object.keys(extras).length) fd.append('extras', JSON.stringify(extras))
  if (posId) fd.append('pos_id', String(posId))
  return http.post('/ai-screen/intake', fd, { timeout: 180000 }) // AI 可能想得慢，多等一会
}

// ---- 面试评价 ----
// 贴逐字稿 → 返回按固定模板写好的评价文字（后端不落库）
// 逐字稿比简历长、AI 写得也慢，超时要放大（默认只有 60 秒）
export const interviewApi = {
  evaluate: (transcript) => http.post('/interview/evaluate', { transcript }, { timeout: 180000 }),
}

// ---- 汇总导出 ----
export const exportFields = () => http.get('/export/fields')

// 导出文件：后端返回的不是 JSON 而是文件字节，所以要特殊处理
// 返回 { blob, filename, rowCount }；导出失败时抛错（拦截器会弹中文提示）
// mode: 'records' 逐条记录（默认）；'matrix' 阶段×岗位交叉汇总表
export async function exportFile(filters, fields, format, mode = 'records', range = 'week') {
  const resp = await http.post('/export', { filters, fields, format, mode, range }, { responseType: 'blob', silent: false })
  // 此时 resp 是完整的 axios 响应（blob 没走成功拦截器的 data 提取，保持原样）
  const cd = resp.headers['content-disposition'] || ''
  // 后端用 filename*=UTF-8''投递记录_xxx.xlsx 的形式给文件名，这里解析出来
  let filename = `投递记录_${Date.now()}.${format}`
  const m = cd.match(/filename\*=UTF-8''([^;]+)/i)
  if (m) filename = decodeURIComponent(m[1])
  const rowCount = Number(resp.headers['x-row-count'] || 0)
  return { blob: resp.data, filename, rowCount }
}
