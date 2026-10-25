/**
 * 【候选人端登录状态】
 * 与管理端完全分开存：ats_portal_token / ats_portal_user / ats_portal_candidate。
 * 这样同一个浏览器可以同时登录 HR 和候选人，互不踢线（联调时很有用）。
 */
import { computed, ref } from 'vue'

const TOKEN_KEY = 'ats_portal_token'
const USER_KEY = 'ats_portal_user'
const CANDIDATE_KEY = 'ats_portal_candidate'

function readJson(key) {
  try {
    return JSON.parse(localStorage.getItem(key) || 'null')
  } catch {
    return null
  }
}

const token = ref(localStorage.getItem(TOKEN_KEY) || '')
const user = ref(readJson(USER_KEY))
const candidate = ref(readJson(CANDIDATE_KEY))

export const portalAuth = {
  token,
  user,
  candidate,
  isLoggedIn: computed(() => !!token.value),
  displayName: computed(() => candidate.value?.name || '候选人'),

  setAuth(newToken, newUser, newCandidate) {
    token.value = newToken
    user.value = newUser || null
    candidate.value = newCandidate || null
    localStorage.setItem(TOKEN_KEY, newToken)
    localStorage.setItem(USER_KEY, JSON.stringify(newUser || null))
    localStorage.setItem(CANDIDATE_KEY, JSON.stringify(newCandidate || null))
  },

  setProfile(newUser, newCandidate) {
    user.value = newUser || user.value
    candidate.value = newCandidate || candidate.value
    localStorage.setItem(USER_KEY, JSON.stringify(user.value))
    localStorage.setItem(CANDIDATE_KEY, JSON.stringify(candidate.value))
  },

  clear() {
    token.value = ''
    user.value = null
    candidate.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(CANDIDATE_KEY)
  },
}
