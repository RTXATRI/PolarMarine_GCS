<template>
  <nav class="side-nav">
    <el-menu
      :default-active="activeIndex"
      :router="false"
      class="menu"
      @select="onSelect"
    >
      <el-menu-item v-for="item in items" :key="item.path" :index="item.path">
        <el-icon><component :is="item.icon" /></el-icon>
        <span>{{ item.label }}</span>
      </el-menu-item>
    </el-menu>

    <div class="footer">
      <div class="hint mono">v0.1.0</div>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed, markRaw } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Histogram,
  Position,
  Cpu,
  Compass,
  Setting,
  Bell
} from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()

const items = [
  { path: '/overview', label: '总览', icon: markRaw(Histogram) },
  { path: '/map', label: '地图态势', icon: markRaw(Position) },
  { path: '/manual', label: '手动控制', icon: markRaw(Cpu) },
  { path: '/mission', label: '任务管理', icon: markRaw(Compass) },
  { path: '/parameters', label: '参数配置', icon: markRaw(Setting) },
  { path: '/logs', label: '日志报警', icon: markRaw(Bell) }
]

const activeIndex = computed(() => route.path)

function onSelect(path: string) {
  if (path !== route.path) {
    router.push(path)
  }
}
</script>

<style scoped>
.side-nav {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.menu {
  flex: 1;
  padding-top: 8px;
}
.menu :deep(.el-menu-item) {
  margin: 2px 8px;
  border-radius: 6px;
  height: 38px;
  line-height: 38px;
  font-size: 13px;
}
.footer {
  border-top: 1px solid var(--border);
  padding: 10px 14px;
  font-size: 11px;
  color: var(--text-muted);
}
.hint {
  line-height: 1.6;
}
</style>
