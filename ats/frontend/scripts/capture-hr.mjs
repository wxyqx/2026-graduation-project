/**
 * HR 端截图脚本（开发辅助）
 * 依赖：Chrome --remote-debugging-port=9223；Vite dev 5174；演示数据 JSON。
 */
import fs from 'node:fs'
import path from 'node:path'

const DEMO = process.env.HR_DEMO_JSON || path.join(process.env.TEMP, 'hr-demo.json')
const OUT = process.env.HR_SHOT_DIR || path.join(process.cwd(), 'hr-shots')
const BASE = 'http://127.0.0.1:5174'
const CDP = 'http://127.0.0.1:9223'
const demo = JSON.parse(fs.readFileSync(DEMO, 'utf8'))
fs.mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const res = await fetch(`${CDP}/json/new?${encodeURIComponent(`${BASE}/login`)}`, { method: 'PUT' })
const target = await res.json()
const ws = new WebSocket(target.webSocketDebuggerUrl)
let seq = 0
const pending = new Map()
ws.addEventListener('message', (e) => {
  const msg = JSON.parse(e.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
  }
})
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true })
  ws.addEventListener('error', reject, { once: true })
})
const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++seq
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
  })
const evaluate = (expression) => send('Runtime.evaluate', { expression, returnByValue: true })
const goto = async (url, wait = 1700) => {
  await send('Page.navigate', { url })
  await sleep(wait)
}
const shot = async (name, width = 1440, height = 900) => {
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
  await sleep(300)
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  fs.writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(data, 'base64'))
  console.log('saved', name)
}
const clickText = async (selector, text) => {
  const ok = await evaluate(`(() => {
    const els = [...document.querySelectorAll(${JSON.stringify(selector)})];
    const el = els.find((e) => (e.textContent || '').trim().includes(${JSON.stringify(text)}));
    if (el) { el.click(); return true; } return false;
  })()`)
  await sleep(900)
  return ok.result?.value
}

await send('Page.enable')
await send('Runtime.enable')
await goto(`${BASE}/login`)
await evaluate(
  `localStorage.setItem('ats_token', ${JSON.stringify(demo.hr_token)});` +
    `localStorage.setItem('ats_user', ${JSON.stringify(JSON.stringify(demo.hr_user))});`,
)

await goto(`${BASE}/candidates`)
await shot('hr-01-candidates')
await clickText('.el-table .link-btn', '陈晨')
await shot('hr-02-candidate-basic')
await clickText('.el-tabs__item', '文件')
await shot('hr-03-candidate-files')
await clickText('.el-tabs__item', '表单答卷')
await shot('hr-04-candidate-forms')

await goto(`${BASE}/applications`)
await shot('hr-05-applications')
await goto(`${BASE}/applications/${demo.application_id}`, 2200)
await shot('hr-06-application-detail', 1440, 1600)

await goto(`${BASE}/form-templates`)
await shot('hr-07-form-templates')
await clickText('button', '字段')
await shot('hr-08-form-fields', 1440, 1000)

ws.close()
