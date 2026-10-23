<template>
  <nav class="side-navigation" aria-label="主导航">
    <el-menu :default-active="activePath" class="menu" @select="navigate">
      <el-menu-item v-for="item in primaryItems" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
      <div class="tool-divider"><span>系统工具</span></div>
      <el-menu-item v-for="item in toolItems" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </el-menu>
    <div class="footer">
      <div class="mono">PolarMarine GCS v1.0.0</div>
      <div>实机工程版</div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Bell,
  Compass,
  Cpu,
  Histogram,
  Management,
  Monitor,
  Position,
  Setting
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const primaryItems = [
  { path: '/', label: '总览', icon: markRaw(Histogram) },
  { path: '/map', label: '地图态势', icon: markRaw(Position) },
  { path: '/manual', label: '手动控制', icon: markRaw(Cpu) },
  { path: '/mission', label: '任务管理', icon: markRaw(Compass) },
  { path: '/parameters', label: '参数配置', icon: markRaw(Setting) },
  { path: '/logs', label: '日志报警', icon: markRaw(Bell) }
]
const toolItems = [
  { path: '/devices', label: '设备管理', icon: markRaw(Management) },
  { path: '/ros-debug', label: 'ROS 调试', icon: markRaw(Monitor) }
]
const activePath = computed(() => route.path)

function navigate(path: string): void {
  if (path !== route.path) void router.push(path)
}
</script>

<style scoped>
.side-navigation {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.menu {
  flex: 1;
  padding-top: 8px;
  overflow-y: auto;
  border-right: 0;
  background: transparent;
}

.menu :deep(.el-menu-item) {
  height: 38px;
  margin: 2px 8px;
  border-radius: 6px;
  color: var(--text-2);
  font-size: 13px;
  line-height: 38px;
}

.menu :deep(.el-menu-item:hover) {
  color: var(--text-1);
  background: var(--bg-hover);
}

.menu :deep(.el-menu-item.is-active) {
  color: var(--color-accent);
  background: rgb(59 130 246 / 12%);
}

.tool-divider {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 14px 14px 7px;
  color: var(--text-muted);
  font-size: 9px;
  letter-spacing: 0.12em;
}

.tool-divider::after {
  flex: 1;
  height: 1px;
  background: var(--border);
  content: '';
}

.footer {
  padding: 9px 14px;
  color: var(--text-muted);
  border-top: 1px solid var(--border);
  font-size: 10px;
  line-height: 1.55;
}
</style>
