/**
 * 【这个文件是干什么的？】——前端的总开关
 * 创建 Vue 应用，装上 Element Plus（组件库）、所有图标、路由，套上主题，然后挂到页面上。
 */
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import * as Icons from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css' // 黑夜模式的颜色变量

import App from './App.vue'
import router from './router'
import { initTheme } from './theme'
import './styles/theme.css'

initTheme() // 先套主题，避免页面闪一下白

const app = createApp(App)
app.use(ElementPlus)
// 把所有图标注册成全局组件，模板里直接写 <el-icon><Briefcase /></el-icon>
for (const [name, comp] of Object.entries(Icons)) {
  app.component(name, comp)
}
app.use(router)
app.mount('#app')
