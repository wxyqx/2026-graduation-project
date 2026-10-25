/**
 * 【候选人端的「电话机」】
 * 和 HR 端的 http.js 是两套：token 不同、登录页不同、baseURL 是 /api/portal。
 *
 * 自动化：
 *   1. 自动带候选人 token
 *   2. 401 → 清登录状态 → 跳 /portal/login
 *   3. 出错统一弹中文提示（silent:true 时调用方自己处理）
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from '../router'
import { portalAuth } from '../stores/portalAuth'

const portalHttp = axios.create({ baseURL: '/api/portal', timeout: 60000 })

portalHttp.interceptors.request.use((config) => {
  if (portalAuth.token.value) {
    config.headers.Authorization = `Bearer ${portalAuth.token.value}`
  }
  return config
})

portalHttp.interceptors.response.use(
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
      portalAuth.clear()
      ElMessage.warning('登录已过期，请重新登录')
      router.push({ name: 'portal-login', query: { redirect: router.currentRoute.value.fullPath } })
    } else if (!error.config?.silent) {
      ElMessage.error(detail)
    }
    error.detail = detail
    return Promise.reject(error)
  },
)

export default portalHttp
