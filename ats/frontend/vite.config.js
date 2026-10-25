import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'

// 后端地址：默认 8000；本机若 8000 被旧进程占用，可用环境变量临时指到 8001：
//   $env:VITE_API_TARGET='http://127.0.0.1:8001'; npm run dev
const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': apiTarget,
    },
  },
})
