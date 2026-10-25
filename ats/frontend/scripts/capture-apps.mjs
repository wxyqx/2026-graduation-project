import fs from 'node:fs'
import path from 'node:path'

const DEMO = JSON.parse(fs.readFileSync(process.env.APPS_DEMO_JSON, 'utf8'))
const OUT = process.env.APPS_SHOT_DIR
const BASE = 'http://127.0.0.1:5174'
const CDP = 'http://127.0.0.1:9223'
fs.mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const res = await fetch(`${CDP}/json/new?${encodeURIComponent(`${BASE}/portal/login`)}`, { method: 'PUT' })
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
await send('Page.enable')
await send('Runtime.enable')
await send('Page.navigate', { url: `${BASE}/portal/login` })
await sleep(1200)
await evaluate(
  `localStorage.setItem('ats_portal_token', ${JSON.stringify(DEMO.token)});` +
    `localStorage.setItem('ats_portal_user', ${JSON.stringify(JSON.stringify(DEMO.user))});` +
    `localStorage.setItem('ats_portal_candidate', ${JSON.stringify(JSON.stringify(DEMO.candidate))});`,
)
async function shot(name, width, height, mobile) {
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: mobile ? 2 : 1, mobile })
  await send('Page.navigate', { url: `${BASE}/portal/applications?t=${Date.now()}` })
  await sleep(1800)
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  fs.writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(data, 'base64'))
  console.log('saved', name)
}
await shot('apps-desktop-1440', 1440, 900, false)
await shot('apps-mobile-375', 375, 812, true)
ws.close()
