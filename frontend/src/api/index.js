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
}

// ---- 岗位 ----
export const positionApi = {
  list: () => http.get('/positions'),
  create: (data) => http.post('/positions', data),
  update: (id, data) => http.put(`/positions/${id}`, data),
  remove: (id) => http.delete(`/positions/${id}`),
}

// ---- 候选人 ----
export const candidateApi = {
  list: (name) => http.get('/candidates', { params: name ? { name } : {} }),
  create: (data) => http.post('/candidates', data),
  update: (id, data) => http.put(`/candidates/${id}`, data),
  remove: (id) => http.delete(`/candidates/${id}`), // 级联删除：连带删掉他名下的投递
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
}

// ---- 统计 ----
export const statsApi = {
  overview: () => http.get('/stats/overview'),
}

// ---- AI 录入简历 ----
// files: 浏览器 File 对象数组（PDF）；texts: 粘贴的纯文本数组；extras: 各岗位的附加条件 {"岗位id": "文字"}
export async function uploadIntake(files, texts, extras = {}) {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  for (const t of texts) fd.append('texts', t)
  if (extras && Object.keys(extras).length) fd.append('extras', JSON.stringify(extras))
  return http.post('/ai-screen/intake', fd, { timeout: 180000 }) // AI 可能想得慢，多等一会
}

// ---- AI 接口配置 ----
export const aiConfigApi = {
  list: () => http.get('/ai-configs'),
  create: (data) => http.post('/ai-configs', data),
  update: (id, data) => http.put(`/ai-configs/${id}`, data),
  remove: (id) => http.delete(`/ai-configs/${id}`),
  enable: (id) => http.put(`/ai-configs/${id}/enable`),
  disable: (id) => http.put(`/ai-configs/${id}/disable`),
}

// ---- 汇总导出 ----
export const exportFields = () => http.get('/export/fields')

// 导出文件：后端返回的不是 JSON 而是文件字节，所以要特殊处理
// 返回 { blob, filename, rowCount }；导出失败时抛错（拦截器会弹中文提示）
export async function exportFile(filters, fields, format) {
  const resp = await http.post('/export', { filters, fields, format }, { responseType: 'blob', silent: false })
  // 此时 resp 是完整的 axios 响应（blob 没走成功拦截器的 data 提取，保持原样）
  const cd = resp.headers['content-disposition'] || ''
  // 后端用 filename*=UTF-8''投递记录_xxx.xlsx 的形式给文件名，这里解析出来
  let filename = `投递记录_${Date.now()}.${format}`
  const m = cd.match(/filename\*=UTF-8''([^;]+)/i)
  if (m) filename = decodeURIComponent(m[1])
  const rowCount = Number(resp.headers['x-row-count'] || 0)
  return { blob: resp.data, filename, rowCount }
}
