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
  // includeHidden=true 时连「暂不招」的岗位一起返回（岗位管理页用）；默认只返回在招的
  list: (includeHidden = false) => http.get('/positions', { params: includeHidden ? { include_hidden: true } : {} }),
  create: (data) => http.post('/positions', data),
  update: (id, data) => http.put(`/positions/${id}`, data),
  remove: (id) => http.delete(`/positions/${id}`),
}

// ---- 候选人 ----
export const candidateApi = {
  // 参数可以是字符串（当姓名搜索用）或对象（{name, remark, has_application}）
  list: (query) => http.get('/candidates', { params: typeof query === 'string' ? (query ? { name: query } : {}) : (query || {}) }),
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
  // 阶段 × 岗位 交叉汇总表；params 例：{range:'week'} 或 {range:'custom', start_date, end_date}
  matrix: (params) => http.get('/stats/matrix', { params }),
  // 进行中的候选人所处阶段清单
  inProgress: (params) => http.get('/stats/in-progress', { params }),
  // 交叉表某个格子里具体是哪些人
  matrixCell: (params) => http.get('/stats/matrix/cell', { params }),
}

// ---- 系统设置（阶段文案改写）----
export const settingsApi = {
  // note 传空 = 恢复自动生成
  saveStageNote: (appId, note) => http.put('/settings/stage-note', { app_id: appId, note }),
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

// ---- AI 筛选提示词（系统设置）----
export const promptApi = {
  get: () => http.get('/settings/ai-prompt'),
  save: (rules) => http.put('/settings/ai-prompt', { rules }),
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
