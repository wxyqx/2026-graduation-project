/**
 * 【技术管理端的「电话机」】
 * token 与 HR / 候选人完全分开：ats_tech_token。
 * 401 → 清空技术端登录状态 → 跳 /tech/login。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from '../router'
import { techAuth } from '../stores/techAuth'

const techHttp = axios.create({ baseURL: '/api/tech', timeout: 60000 })

techHttp.interceptors.request.use((config) => {
  if (techAuth.token.value) config.headers.Authorization = `Bearer ${techAuth.token.value}`
  return config
})

techHttp.interceptors.response.use(
  (response) => {
    if (response.config.responseType === 'blob') return response
    return response.data
  },
  async (error) => {
    const status = error.response?.status
    let data = error.response?.data
    const isAuthApi = (error.config?.url || '').includes('/auth/')
    if (data instanceof Blob) {
      try {
        const text = await data.text()
        const parsed = JSON.parse(text)
        data = parsed.detail ? { detail: parsed.detail } : parsed
      } catch {
        data = null
      }
    }
    const detail =
      typeof data?.detail === 'string' ? data.detail : data?.message || error.message || '请求失败'
    if (status === 401 && !isAuthApi) {
      techAuth.clear()
      ElMessage.warning('登录已过期，请重新登录')
      router.push({ name: 'tech-login', query: { redirect: router.currentRoute.value.fullPath } })
    } else if (!error.config?.silent) {
      ElMessage.error(detail)
    }
    error.detail = detail
    return Promise.reject(error)
  },
)

export default techHttp
