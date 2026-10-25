/** 【技术管理端登录状态】与 HR / 候选人 token 完全分开。 */
import { computed, ref } from 'vue'

const TOKEN_KEY = 'ats_tech_token'
const USER_KEY = 'ats_tech_user'

function readJson(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null')
  } catch {
    return null
  }
}

const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const user = ref(readJson(USER_KEY))

export const techAuth = {
  token,
  user,
  isLoggedIn: computed(() => !!token.value),
  displayName: computed(() => user.value?.real_name || user.value?.username || '技术管理员'),

  setAuth(newToken, newUser) {
    token.value = newToken
    user.value = newUser || null
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser || null))
  },

  setUser(newUser) {
    user.value = newUser || user.value
    localStorage.setItem(USER_KEY, JSON.stringify(user.value))
  },

  clear() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
}
