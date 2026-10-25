/**
 * 候选人端截图脚本（开发辅助，不参与打包）
 * 依赖：本机 Chrome 以 --remote-debugging-port=9223 启动；Vite dev 在 5174。
 * 用法：node scripts/capture-portal.mjs
 */
import fs from 'node:fs'
import path from 'node:path'

const DEMO = process.env.PORTAL_DEMO_JSON || path.join(process.env.TEMP, 'portal-demo.json')
const OUT = process.env.PORTAL_SHOT_DIR || path.join(process.cwd(), 'portal-shots')
const BASE = 'http://127.0.0.1:5174'
const CDP = 'http://127.0.0.1:9223'

const demo = JSON.parse(fs.readFileSync(DEMO, 'utf8'))
fs.mkdirSync(OUT, { recursive: true })

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function newTarget(url) {
  const res = await fetch(`${CDP}/json/new?${encodeURIComponent(url)}`, { method: 'PUT' })
  if (!res.ok) throw new Error(`new target failed: ${res.status}`)
  return res.json()
}

const target = await newTarget(`${BASE}/portal/login`)
const ws = new WebSocket(target.webSocketDebuggerUrl)
let seq = 0
const pending = new Map()

ws.addEventListener('message', (event) => {
  const msg = JSON.parse(event.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    if (msg.error) reject(new Error(JSON.stringify(msg.error)))
    else resolve(msg.result)
  }
})

await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true })
  ws.addEventListener('error', reject, { once: true })
})

function send(method, params = {}) {
  const id = ++seq
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
  })
}

async function evaluate(expression) {
  return send('Runtime.evaluate', { expression, returnByValue: true })
}

async function goto(url) {
  await send('Page.navigate', { url })
  await sleep(1600)
  // 等 SPA 完成一次数据请求
  await sleep(600)
}

async function setAuth() {
  const token = JSON.stringify(demo.token)
  const user = JSON.stringify(JSON.stringify(demo.user))
  const cand = JSON.stringify(JSON.stringify(demo.candidate))
  await evaluate(
    `localStorage.setItem('ats_portal_token', ${token});` +
      `localStorage.setItem('ats_portal_user', ${user});` +
      `localStorage.setItem('ats_portal_candidate', ${cand});`,
  )
}

async function shot(name, url, width, height, { mobile = true, auth = true } = {}) {
  await send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: mobile ? 2 : 1,
    mobile,
  })
  if (auth) {
    await goto(`${BASE}/portal/login`)
    await setAuth()
  } else {
    await goto(`${BASE}/portal/login`)
    await evaluate('localStorage.clear()')
  }
  await goto(url)
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  const file = path.join(OUT, `${name}.png`)
  fs.writeFileSync(file, Buffer.from(data, 'base64'))
  console.log('saved', file)
}

await send('Page.enable')
await send('Runtime.enable')

const pos = demo.position_id
const app = demo.application_id

await shot('01-login-375', `${BASE}/portal/login`, 375, 812, { auth: false })
await shot('02-positions-375', `${BASE}/portal/positions`, 375, 812)
await shot('03-positions-1440', `${BASE}/portal/positions`, 1440, 900, { mobile: false })
await shot('04-position-detail-375', `${BASE}/portal/positions/${pos}`, 375, 812)
await shot('05-applications-375', `${BASE}/portal/applications`, 375, 812)
await shot('06-application-detail-375', `${BASE}/portal/applications/${app}`, 375, 812)
await shot('07-files-375', `${BASE}/portal/files`, 375, 812)
await shot('08-profile-375', `${BASE}/portal/profile`, 375, 812)
await shot('09-form-profile-375', `${BASE}/portal/forms/${demo.template_profile}`, 375, 812)
await shot(
  '10-form-position-375',
  `${BASE}/portal/forms/${demo.template_position}?application_id=${app}`,
  375,
  812,
)

ws.close()
