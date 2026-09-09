/**
 * 【这个文件是干什么的？】
 * 小工具：把后端给的时间字符串（2026-09-08T14:30:00）变成好看的「2026-09-08 14:30」。
 */
export function fmtTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value
  const p = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}
