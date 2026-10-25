/** 【技术管理端接口清单】 */
import techHttp from './techHttp'

export const techAuthApi = {
  login: (username, password) => techHttp.post('/auth/login', { username, password }, { silent: true }),
  me: () => techHttp.get('/auth/me'),
  changePassword: (current_password, new_password) =>
    techHttp.put('/auth/password', { current_password, new_password }),
    updateAvatar: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return techHttp.put('/auth/avatar', fd)
  },
  avatarBlob: () => techHttp.get('/auth/avatar', { responseType: 'blob', silent: true }),
}

export const techOverviewApi = {
  get: () => techHttp.get('/overview'),
}

export const techAccountApi = {
  list: (params) => techHttp.get('/accounts', { params }),
  create: (data) => techHttp.post('/accounts', data),
  setStatus: (id, isActive) => techHttp.put(`/accounts/${id}/status`, { is_active: isActive }),
  resetPassword: (id) => techHttp.put(`/accounts/${id}/reset-password`),
}

export const techStageOwnerApi = {
  list: (keyword) => techHttp.get('/candidate-owners/stage-owners', { params: keyword ? { keyword } : {} }),
  setOwners: (appId, owners) => techHttp.put(`/candidate-owners/stage-owners/${appId}`, { owners }),
}

export const techCandidateOwnerApi = {
  list: (keyword) => techHttp.get('/candidate-owners', { params: keyword ? { keyword } : {} }),
  setOwner: (id, owner_id) => techHttp.put(`/candidate-owners/${id}`, { owner_id }),
  batchSetOwner: (candidate_ids, owner_id) => techHttp.put('/candidate-owners/batch', { candidate_ids, owner_id }),
}

export const techEmailApi = {
  get: () => techHttp.get('/email-smtp'),
  save: (data) => techHttp.put('/email-smtp', data),
  test: (to) => techHttp.post('/email-smtp/test', { to }),
}

export const techConfigApi = {
  list: () => techHttp.get('/ai-configs'),
  create: (data) => techHttp.post('/ai-configs', data),
  update: (id, data) => techHttp.put(`/ai-configs/${id}`, data),
  remove: (id) => techHttp.delete(`/ai-configs/${id}`),
  enable: (id) => techHttp.put(`/ai-configs/${id}/enable`),
  disable: (id) => techHttp.put(`/ai-configs/${id}/disable`),
  getPrompt: () => techHttp.get('/ai-prompt'),
  savePrompt: (rules) => techHttp.put('/ai-prompt', { rules }),
}

export const techLogApi = {
  list: (params) => techHttp.get('/logs', { params }),
}

export const techBackupApi = {
  async download() {
    const resp = await techHttp.get('/backup/export', { responseType: 'blob' })
    const cd = resp.headers['content-disposition'] || ''
    let filename = `ats_backup_${Date.now()}.zip`
    const m = cd.match(/filename\*=UTF-8''([^;]+)/i)
    if (m) filename = decodeURIComponent(m[1])
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    return { filename, rows: Number(resp.headers['x-backup-rows'] || 0) }
  },
}
