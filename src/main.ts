import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './styles/index.scss'

import { useThemeStore } from '@/stores/theme'
import { useSystemStore } from '@/stores/system'
import { startBackendDataSource } from '@/services/data-source'

function bootstrap() {
  const app = createApp(App)
  const pinia = createPinia()

  app.use(pinia)
  app.use(router)
  app.use(ElementPlus)

  for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
    app.component(name, component)
  }

  // 启动主题(读取持久化)、系统时钟与数据源
  useThemeStore() // 触发 store 创建,内部应用主题到 DOM
  useSystemStore().startClock()

  app.mount('#app')
  // Render the application shell immediately. Backend startup/reconnect runs in
  // the background so a stopped service can be diagnosed and recovered from.
  void startBackendDataSource()
}

bootstrap()
