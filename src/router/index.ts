import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: '/overview' },
  {
    path: '/overview',
    name: 'overview',
    meta: { title: '总览' },
    component: () => import('@/views/OverviewView.vue')
  },
  {
    path: '/map',
    name: 'map',
    meta: { title: '地图态势' },
    component: () => import('@/views/MapView.vue')
  },
  {
    path: '/manual',
    name: 'manual',
    meta: { title: '手动控制' },
    component: () => import('@/views/ManualControlView.vue')
  },
  {
    path: '/mission',
    name: 'mission',
    meta: { title: '任务管理' },
    component: () => import('@/views/MissionView.vue')
  },
  {
    path: '/parameters',
    name: 'parameters',
    meta: { title: '参数配置' },
    component: () => import('@/views/ParameterView.vue')
  },
  {
    path: '/logs',
    name: 'logs',
    meta: { title: '日志报警' },
    component: () => import('@/views/LogAlarmView.vue')
  }
]

export const router = createRouter({
  history: createWebHashHistory(),
  routes
})

export default router
