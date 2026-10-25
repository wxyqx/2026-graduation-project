/** 技术管理端截图脚本（开发辅助） */
import fs from 'node:fs'
import path from 'node:path'

const DEMO = process.env.TECH_DEMO_JSON || path.join(process.env.TEMP, 'tech-demo.json')
const OUT = process.env.TECH_SHOT_DIR || path.join(process.cwd(), 'tech-shots')
const BASE = 'http://127.0.0.1:5174'
const CDP = 'http://127.0.0.1:9223'
const demo = JSON.parse(fs.readFileSync(DEMO, 'utf8'))
fs.mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const res = await fetch(`${CDP}/json/new?${encodeURIComponent(`${BASE}/tech/login`)}`, { method: 'PUT' })
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
const goto = async (url, wait = 1600) => {
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

await send('Page.enable')
await send('Runtime.enable')

await goto(`${BASE}/tech/login`)
await evaluate('localStorage.clear()')
await goto(`${BASE}/tech/login`)
await shot('tech-01-login')

await evaluate(
  `localStorage.setItem('ats_tech_token', ${JSON.stringify(demo.token)});` +
    `localStorage.setItem('ats_tech_user', ${JSON.stringify(JSON.stringify(demo.user))});`,
)
await goto(`${BASE}/tech`)
await shot('tech-02-overview', 1440, 1000)
await goto(`${BASE}/tech/accounts`)
await shot('tech-03-accounts')
await goto(`${BASE}/tech/config`)
await shot('tech-04-config', 1440, 1000)
await goto(`${BASE}/tech/logs`)
await shot('tech-05-logs')
await goto(`${BASE}/tech/backup`)
await shot('tech-06-backup')

ws.close()
