import fs from 'node:fs'
import path from 'node:path'

const DEMO = JSON.parse(fs.readFileSync(process.env.FORM_DEMO_JSON, 'utf8'))
const OUT = process.env.FORM_SHOT_DIR
const BASE = process.env.FORM_BASE || 'http://127.0.0.1:5174'
const CDP = 'http://127.0.0.1:9223'
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
await send('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
await send('Page.navigate', { url: `${BASE}/portal/login` })
await sleep(1000)
await evaluate(
  `localStorage.setItem('ats_portal_token', ${JSON.stringify(DEMO.token)});` +
    `localStorage.setItem('ats_portal_user', ${JSON.stringify(JSON.stringify(DEMO.user))});` +
    `localStorage.setItem('ats_portal_candidate', ${JSON.stringify(JSON.stringify(DEMO.candidate))});`,
)
await send('Page.navigate', { url: `${BASE}/portal/forms/${DEMO.template_id}?t=${Date.now()}` })
await sleep(1600)
const rects = await evaluate(
  `[...document.querySelectorAll('.color-slider')].slice(0,4).map(el => { const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height} })`,
)
for (let i = 0; i < 3; i++) {
  const r = rects.result.value[i]
  const ratio = i === 0 ? 0.01 : i === 1 ? 0.5 : 0.99
  const x = r.x + r.w * ratio
  const y = r.y + r.h / 2
  await send('Input.dispatchMouseEvent', { type: 'mousePressed', x, y, button: 'left', clickCount: 1 })
  await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x, y, button: 'left', clickCount: 1 })
}
await sleep(500)
await evaluate(`document.querySelectorAll('.color-slider')[3].scrollIntoView({ block: 'center' })`)
await sleep(300)
const rects2 = await evaluate(
  `[...document.querySelectorAll('.color-slider')].slice(0,4).map(el => { const r=el.getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height} })`,
)
const r = rects2.result.value[3]
const sx = r.x + 2
const sy = r.y + r.h / 2
await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: sx, y: sy, button: 'left', clickCount: 1 })
await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: r.x + r.w * 0.25, y: sy, button: 'left', buttons: 1 })
await sleep(600)
{
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  fs.writeFileSync(path.join(OUT, 'form-color-dragging.png'), Buffer.from(data, 'base64'))
  console.log('saved form-color-dragging')
}
await sleep(600)
const during = await evaluate(`document.querySelectorAll('.color-fill')[3].style.background`)
console.log('during drag:', during.result.value)
await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: r.x + r.w * 0.25, y: sy, button: 'left', clickCount: 1 })
await sleep(200)
const after = await evaluate(`document.querySelectorAll('.color-fill')[3].style.background`)
console.log('after snap:', after.result.value)
const state = await evaluate(
  `({thumbs:document.querySelectorAll('.color-thumb').length, fills:[...document.querySelectorAll('.color-fill')].slice(0,3).map(x=>x.style.background)})`,
)
console.log(JSON.stringify(state.result.value))
const { data } = await send('Page.captureScreenshot', { format: 'png' })
fs.writeFileSync(path.join(OUT, 'form-color-states.png'), Buffer.from(data, 'base64'))
console.log('saved form-color-states')
ws.close()
