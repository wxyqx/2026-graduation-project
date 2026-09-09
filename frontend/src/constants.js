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
