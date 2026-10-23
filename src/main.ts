import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import 'maplibre-gl/dist/maplibre-gl.css'
import App from '@/app/App.vue'
import { router } from '@/app/router'
import { useThemeStore } from '@/app/theme-store'
import { startDataSource, stopDataSource } from '@/shared/api/data-source'
import '@/styles/index.scss'

const application = createApp(App)
const pinia = createPinia()
application.use(pinia)
application.use(router)
application.use(ElementPlus)
useThemeStore(pinia)
application.mount('#app')

void startDataSource()
window.addEventListener('beforeunload', stopDataSource, { once: true })
