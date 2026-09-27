/**
 * 【这个文件是干什么的？】
 * 存「每个岗位的 AI 附加筛选条件」。
 *
 * 为什么要单独存这里？因为按设计要求，这段文字**不进数据库**——它只是你临时给 AI 加的额外限制
 * （比如「只要 985/211」「必须有医疗行业项目经验」），但刷新后还想保住，所以放浏览器的 localStorage。
 *
 * 用法：key 是岗位编号，value 是那段限制文字。岗位被删除时记得调 remove 一起清掉。
 */
import { reactive } from 'vue'

const KEY = 'ats_position_extras' // localStorage 里的存储名

// 从 localStorage 读出已有的（形如 {"1": "只要985", "6": "..."}）
const map = reactive(JSON.parse(localStorage.getItem(KEY) || '{}'))

function persist() {
  localStorage.setItem(KEY, JSON.stringify(map))
}

export const positionExtras = {
  map, // 直接读它做响应式显示
  /** 取某个岗位的附加条件（没有就返回空字符串） */
  get(id) {
    return map[id] || ''
  },
  /** 有就存、空就删 */
  set(id, text) {
    const t = (text || '').trim()
    if (t) map[id] = t
    else delete map[id]
    persist()
  },
  /** 岗位被删时清掉它的附加条件 */
  remove(id) {
    delete map[id]
    persist()
  },
  /** 这个岗位有没有附加条件（表格里显示小标签用） */
  has(id) {
    return !!map[id]
  },
  /** 导出成 { "1": "text", ... } 的普通对象，提交给后端 */
  all() {
    return { ...map }
  },
}
