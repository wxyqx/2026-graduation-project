/**
 * 【这个文件是干什么的？】
 * 保存「我登录了没、我是谁」。token 和用户信息存在浏览器的 localStorage 里，刷新页面不会丢。
 *
 * 用 Vue 的 ref 包起来，谁引用了它，登录状态一变页面就自动更新。
 * 整个程序只有这一份（单例），所有地方 import 的都是同一个 auth。
 */
import { computed, ref } from 'vue'

const TOKEN_KEY = 'ats_token'
const USER_KEY = 'ats_user'

const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const user = ref(JSON.parse(localStorage.getItem(USER_KEY) || 'null'))

export const auth = {
  token,
  user,
  isLoggedIn: computed(() => !!token.value),

  /** 登录 / 注册成功后调用：把通行证和用户信息存起来 */
  setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
  },

  /** 只更新用户信息（改用户名后刷新顶栏显示，token 另行 setAuth 替换） */
  setUser(newUser) {
    user.value = newUser
    localStorage.setItem(USER_KEY, JSON.stringify(newUser))
  },

  /** 退出登录 / token 失效时调用：全部清掉 */
  clear() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
}
