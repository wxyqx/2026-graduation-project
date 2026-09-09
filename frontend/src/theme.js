/**
 * 【这个文件是干什么的？】
 * 三档主题切换：白天（默认）/ 黑夜 / 护眼。
 *
 * 原理：在 <html> 标签上加不同的 class——
 *   dark      → Element Plus 官方黑夜模式（它的组件会自动变色）
 *   eye-care  → 我们自定义的米黄色变量（见 styles/theme.css）
 * 选择存 localStorage，刷新后还是上次选的。
 */
import { ref } from 'vue'

const KEY = 'ats_theme'

export const THEMES = [
  { value: 'day', label: '白天' },
  { value: 'dark', label: '黑夜' },
  { value: 'eye', label: '护眼' },
]

export const theme = ref(localStorage.getItem(KEY) || 'day')

export function applyTheme(value) {
  const html = document.documentElement
  html.classList.toggle('dark', value === 'dark')
  html.classList.toggle('eye-care', value === 'eye')
  localStorage.setItem(KEY, value)
  theme.value = value
}

/** 程序启动时调一次，把上次选的主题套上 */
export function initTheme() {
  applyTheme(theme.value)
}
