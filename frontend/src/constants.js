/**
 * 【这个文件是干什么的？】
 * 放整个前端都要用的「固定名单」：8 个招聘阶段、3 种整体状态、2 种结果，以及它们的中文名。
 * 所有英文代号都照抄后端的数据字典，改这里一处，全站生效。
 */

// 8 关的顺序（和后端 state_machine.py 里的 STAGES 一致）
export const STAGES = [
  { value: 'ai', label: 'AI筛选' },
  { value: 'resume', label: '简历筛选' },
  { value: 'contact', label: '联系候选人' },
  { value: 'phone', label: '电话沟通' },
  { value: 'test', label: '笔试' },
  { value: 'pro', label: '专业面' },
  { value: 'hr', label: 'HR面' },
  { value: 'final', label: '终面' },
]

// 代号 → 中文，例：STAGE_LABEL.phone === '电话沟通'
export const STAGE_LABEL = Object.fromEntries(STAGES.map((s) => [s.value, s.label]))

// 代号 → 序号（0~7）。管线的深浅、进度推算都靠它
export const STAGE_INDEX = Object.fromEntries(STAGES.map((s, i) => [s.value, i]))

// 8 关的渐变色阶：浅 → 深（越往后颜色越深 = 走得越远）
// 具体色值定义在 styles/theme.css 里，按主题切换；这里只给出变量名
export const STAGE_COLOR = Object.fromEntries(
  STAGES.map((s, i) => [s.value, `var(--ats-stage-${i + 1})`]),
)

// 浅色阶段上的字用深色、深色阶段上的字用白色 —— 保证对比度
export const STAGE_ON_LIGHT = 3 // 前 3 关（第 1~3 关）浅，用深字
export function stageTextColor(index) {
  return index < STAGE_ON_LIGHT ? 'var(--ats-on-light)' : 'var(--ats-on-dark)'
}

// 整体状态：type 是 Element Plus 标签（el-tag）的颜色种类
export const STATUSES = [
  { value: 'pending', label: '进行中', type: 'primary' },
  { value: 'pass', label: '已录用', type: 'success' },
  { value: 'fail', label: '已淘汰', type: 'danger' },
]
export const STATUS_LABEL = Object.fromEntries(STATUSES.map((s) => [s.value, s.label]))
export const STATUS_TYPE = Object.fromEntries(STATUSES.map((s) => [s.value, s.type]))

// 每一关的结果
export const RESULT_LABEL = { pass: '通过', fail: '淘汰' }
