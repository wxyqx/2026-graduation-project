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
