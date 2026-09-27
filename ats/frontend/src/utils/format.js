/**
 * 【这个文件是干什么的？】
 * 小工具：把后端给的时间字符串（2026-09-08T14:30:00）变成好看的「2026-09-08 14:30」。
 *
 * 用 Intl.DateTimeFormat 而不是手工拼 getFullYear/getMonth/...：
 * 日期字段的取法、补零、以及不同语言环境下的数字形式都交给浏览器统一处理。
 * 只需要「年-月-日 时:分」这一种固定版式，所以用 formatToParts 取出各部分再拼，
 * 这样既走 Intl，又保证全站显示格式完全一致（不受运行环境的 locale 影响）。
 */
// formatter 只建一次（构造 Intl 对象有成本，列表里每行都调这里）
const dateTimeFormatter = new Intl.DateTimeFormat('zh-CN', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

export function fmtTime(value) {
  if (!value) return ''
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return value

  // 从 formatToParts 里按类型取，避免依赖某个 locale 的分隔符/顺序
  const parts = {}
  for (const p of dateTimeFormatter.formatToParts(d)) {
    if (p.type !== 'literal') parts[p.type] = p.value
  }
  return `${parts.year}-${parts.month}-${parts.day} ${parts.hour}:${parts.minute}`
}
