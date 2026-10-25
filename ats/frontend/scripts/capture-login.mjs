import fs from 'node:fs'
import path from 'node:path'

const OUT = process.env.LOGIN_SHOT_DIR
const BASE = 'http://127.0.0.1:5174'
const CDP = 'http://127.0.0.1:9223'
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
await send('Page.enable')
await send('Runtime.enable')

async function shot(name, url, width, height, mobile) {
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: mobile ? 2 : 1, mobile })
  await send('Page.navigate', { url })
  await sleep(1200)
  await send('Runtime.evaluate', { expression: 'localStorage.clear()' })
  await send('Page.navigate', { url })
  await sleep(1400)
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  fs.writeFileSync(path.join(OUT, `${name}.png`), Buffer.from(data, 'base64'))
  console.log('saved', name)
}

await shot('login-unified-1440', `${BASE}/login`, 1440, 900, false)
await shot('login-unified-375', `${BASE}/login`, 375, 812, true)
await shot('login-candidate-375', `${BASE}/portal/login`, 375, 812, true)
await shot('login-tech-1440', `${BASE}/tech/login`, 1440, 900, false)
ws.close()
