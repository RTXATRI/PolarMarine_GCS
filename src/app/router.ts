import { createRouter, createWebHistory } from 'vue-router'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'overview',
      component: () => import('@/pages/OverviewPage.vue'),
      meta: { title: '总览' }
    },
    {
      path: '/map',
      name: 'map',
      component: () => import('@/pages/MapPage.vue'),
      meta: { title: '地图态势' }
    },
    {
      path: '/manual',
      name: 'manual',
      component: () => import('@/pages/ManualControlPage.vue'),
      meta: { title: '手动控制' }
    },
    {
      path: '/mission',
      name: 'mission',
      component: () => import('@/pages/MissionPage.vue'),
      meta: { title: '任务编排' }
    },
    {
      path: '/parameters',
      name: 'parameters',
      component: () => import('@/pages/ParametersPage.vue'),
      meta: { title: '参数管理' }
    },
    {
      path: '/logs',
      name: 'logs',
      component: () => import('@/pages/EventsPage.vue'),
      meta: { title: '事件与告警' }
    },
    {
      path: '/devices',
      name: 'devices',
      component: () => import('@/pages/DevicesPage.vue'),
      meta: { title: '设备管理' }
    },
    {
      path: '/ros-debug',
      name: 'ros-debug',
      component: () => import('@/pages/RosDebugPage.vue'),
      meta: { title: 'ROS 调试' }
    }
  ]
})
