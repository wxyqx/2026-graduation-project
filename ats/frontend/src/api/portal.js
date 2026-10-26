/**
 * 【候选人端接口清单】
 * 每个函数对应后端 /api/portal/** 的一个接口；页面里只调函数，不记网址。
 */
import portalHttp from './portalHttp'

export const portalAuthApi = {
  login: (phone, password) => portalHttp.post('/auth/login', { phone, password }, { silent: true }),
  me: () => portalHttp.get('/auth/me'),
  changePassword: (current_password, new_password) =>
    portalHttp.put('/auth/password', { current_password, new_password }),
  // 隐私政策与 AI 筛选告知：投递/填表/回传前必须同意（PIPL 告知-同意）
  privacyPolicy: () => portalHttp.get('/auth/privacy-policy', { silent: true }),
  consentPrivacy: () => portalHttp.post('/auth/privacy-consent'),
  // 头像：上传即替换；获取返回 blob（404 = 未设置，前端显示首字占位）
  updateAvatar: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return portalHttp.put('/auth/avatar', fd)
  },
  avatarBlob: () => portalHttp.get('/auth/avatar', { responseType: 'blob', silent: true }),
}

export const portalPositionApi = {
  list: () => portalHttp.get('/positions'),
  detail: (id) => portalHttp.get(`/positions/${id}`),
}

export const portalApplicationApi = {
  list: () => portalHttp.get('/applications'),
  detail: (id) => portalHttp.get(`/applications/${id}`),
  apply: (posId) => portalHttp.post('/applications', { pos_id: posId }),
}

export const portalFileApi = {
  list: (category) => portalHttp.get('/files', { params: category ? { category } : {} }),
  // 回传文件：签署的录用协议 / Offer / 背景调查 / 其他附件
  uploadReturn: (file, category, applicationId) => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('category', category)
    fd.append('application_id', String(applicationId))
    return portalHttp.post('/files', fd)
  },
  /** 下载要带 token，所以用 axios 取 blob 再触发浏览器保存 */
  async download(file) {
    const res = await portalHttp.get(`/files/${file.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(res.data)
    const a = document.createElement('a')
    a.href = url
    a.download = file.original_name || 'file'
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  },
  /** 预览用：只取原始响应（blob + content-type），由页面自己渲染成 PDF / 图片 */
  blob(file) {
    return portalHttp.get(`/files/${file.id}/download`, { responseType: 'blob' })
  },
  // 自助上传新版简历（挂起待 HR 确认转正）
  uploadResume: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return portalHttp.post('/files/resume', fd)
  },
  removeResume: (id) => portalHttp.delete(`/files/resume/${id}`),
  // 撤回自己回传的文件（传错可自助补救）
  removeReturn: (id) => portalHttp.delete(`/files/returns/${id}`),
}

export const portalFormApi = {
  list: (applicationId) =>
    portalHttp.get('/forms', { params: applicationId ? { application_id: applicationId } : {} }),
  detail: (templateId, applicationId) =>
    portalHttp.get(`/forms/${templateId}`, {
      params: applicationId ? { application_id: applicationId } : {},
    }),
  save: (templateId, answers, submit, applicationId) =>
    portalHttp.put(
      `/forms/${templateId}`,
      { answers, submit },
      { params: applicationId ? { application_id: applicationId } : {} },
    ),
}

// ---- 通知：通过关卡后 HR 模板发送，登录弹窗展示 ----
export const portalNoticeApi = {
  list: () => portalHttp.get('/notices'),
  markRead: (id) => portalHttp.put(`/notices/${id}/read`),
}
