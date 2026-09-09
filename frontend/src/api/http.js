/**
 * 【这个文件是干什么的？】
 * 前端跟后端说话的「电话机」——所有请求都从这里发出去。
 *
 * 两件自动化的事：
 *   1. 发请求前：自动把登录 token 塞进请求头（Authorization: Bearer xxx），页面里不用每次手写
 *   2. 收到回复后：出错时统一弹红色提示；如果是 401（没登录 / 过期），清掉本地登录状态并跳到登录页
 *
 * 想自己处理错误、不要自动弹提示的地方，调用时传 { silent: true }（登录页就是这么干的）。
 */
import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from '../router'
import { auth } from '../stores/auth'

// vite.config.js 里把 /api 代理到了后端 8000 端口，所以这里只写 /api
const http = axios.create({ baseURL: '/api', timeout: 60000 })

http.interceptors.request.use((config) => {
  if (auth.token.value) {
    config.headers.Authorization = `Bearer ${auth.token.value}`
  }
  return config
})

http.interceptors.response.use(
  (response) => {
    // 下载文件这类请求要读响应头（文件名、行数），所以把整个响应交回去
    if (response.config.responseType === 'blob') return response
    return response.data // 其余：直接把 data 给调用方，少写一层 .data
  },
  async (error) => {
    const status = error.response?.status
    let data = error.response?.data
    const isAuthApi = (error.config?.url || '').includes('/auth/')
    // 下载接口出错时返回的也是 blob，把它读成文字再解析出后端的提示
    if (data instanceof Blob) {
      try {
        const text = await data.text()
        const parsed = JSON.parse(text)
        data = parsed.detail ? { detail: parsed.detail } : parsed
      } catch {
        data = null
      }
    }
    // 后端的错误说明在 detail 里（字符串），422 参数错误时 detail 是数组、message 是总说明
    const detail =
      typeof data?.detail === 'string' ? data.detail : data?.message || error.message || '请求失败'

    if (status === 401 && !isAuthApi) {
      auth.clear()
      ElMessage.warning('登录已过期，请重新登录')
      router.push({ name: 'login', query: { redirect: router.currentRoute.value.fullPath } })
    } else if (!error.config?.silent) {
      ElMessage.error(detail)
    }
    error.detail = detail // 方便调用方直接拿中文说明
    return Promise.reject(error)
  },
)

export default http
