<template>
  <div class="topbar">
    <div class="brand">
      <div class="logo" aria-hidden="true">
        <svg viewBox="0 0 64 64" width="22" height="22">
          <circle cx="32" cy="32" r="18" fill="none" stroke="#60a5fa" stroke-width="3" />
          <circle cx="32" cy="32" r="5" fill="#60a5fa" />
          <path d="M32 8 L32 16 M32 48 L32 56 M8 32 L16 32 M48 32 L56 32" stroke="#60a5fa" stroke-width="2" />
        </svg>
      </div>
      <div class="brand-text">
        <div class="title">PolarMarine GCS <span class="beta-tag">Beta</span></div>
        <div class="sub">Ground Control Station</div>
      </div>
    </div>

    <div class="metrics">
      <div class="metric">
        <span class="k">系统状态</span>
        <StatusDot :tone="systemTone" :label="systemLabel" />
      </div>
      <div class="metric">
        <span class="k">当前时间</span>
        <span class="v mono">{{ system.nowText }}</span>
      </div>
      <div class="metric">
        <span class="k">已连接设备</span>
        <span class="v mono">
          <span class="num">{{ system.backendConnected ? robots.onlineCount : '--' }}</span>
          <span class="muted"> / {{ robots.robots.length }}</span>
        </span>
      </div>
      <div class="metric">
        <span class="k">当前设备</span>
        <span class="v mono">{{ robots.selectedId || '--' }}</span>
      </div>
      <div class="metric">
        <span class="k">控制模式</span>
        <span class="tag-pill" :class="modeTone">{{ modeText }}</span>
      </div>
      <div class="metric">
        <span class="k">链路</span>
        <span class="tag-pill" :class="linkTone">
          {{ linkText }}
          <span v-if="linkLatency" class="muted" style="margin-left: 4px">{{ linkLatency }}</span>
        </span>
      </div>
    </div>

    <div class="actions">
      <el-tooltip :content="theme.theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'">
        <el-button circle size="small" @click="theme.toggle()">
          <el-icon v-if="theme.theme === 'dark'"><Sunny /></el-icon>
          <el-icon v-else><Moon /></el-icon>
        </el-button>
      </el-tooltip>
      <EmergencyButton compact />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Sunny, Moon } from '@element-plus/icons-vue'
import StatusDot from '@/components/common/StatusDot.vue'
import EmergencyButton from '@/components/common/EmergencyButton.vue'
import { useRobotsStore } from '@/stores/robots'
import { useSystemStore } from '@/stores/system'
import { useThemeStore } from '@/stores/theme'

const robots = useRobotsStore()
const system = useSystemStore()
const theme = useThemeStore()

const selected = computed(() => robots.selected)

const systemTone = computed<'online' | 'warn' | 'danger'>(() => {
  if (!system.backendConnected) return 'danger'
  const hasAlarm = robots.robots.some(r => r.alarm)
  if (hasAlarm) return 'warn'
  return 'online'
})
const systemLabel = computed(() => {
  if (system.backendState === 'connecting') return '后端连接中'
  if (!system.backendConnected) return '后端连接中断'
  if (robots.robots.length > 0 && robots.onlineCount === 0) return '等待设备连接'
  if (systemTone.value === 'online') return '系统正常'
  if (systemTone.value === 'warn') return '部分异常'
  return '后端连接中断'
})

const modeText = computed(() => system.backendConnected ? (selected.value?.mode ?? '未知') : '未知')
const modeTone = computed(() => {
  if (!system.backendConnected) return 'offline'
  switch (selected.value?.mode) {
    case '手动':
      return 'info'
    case '自动':
      return 'online'
    case '急停':
      return 'danger'
    case '离线':
    default:
      return 'offline'
  }
})

const linkText = computed(() => system.backendConnected ? (selected.value?.linkStatus ?? '未知') : '未知')
const linkTone = computed(() => {
  if (!system.backendConnected) return 'offline'
  switch (selected.value?.linkStatus) {
    case '正常':
      return 'online'
    case '延迟高':
    case '丢包':
      return 'warn'
    case '断开':
      return 'danger'
    default:
      return 'offline'
  }
})
const linkLatency = computed(() => {
  const v = selected.value?.latencyMs
  return !system.backendConnected || v == null ? '' : `${v}ms`
})
</script>

<style scoped>
.topbar {
  height: 100%;
  display: grid;
  grid-template-columns: 220px 1fr auto;
  align-items: center;
  padding: 0 12px;
  gap: 16px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
}
.logo {
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  background: rgba(96, 165, 250, 0.12);
  border-radius: 6px;
}
.title {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-1);
  letter-spacing: 0.04em;
}
.sub {
  font-size: 11px;
  color: var(--text-3);
}
.beta-tag {
  display: inline-block;
  font-size: 9px;
  font-weight: 600;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.4);
  border-radius: 3px;
  padding: 0 4px;
  line-height: 16px;
  vertical-align: middle;
  margin-left: 6px;
  letter-spacing: 0.04em;
}

.metrics {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}
.metric {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.metric .k {
  font-size: 10.5px;
  color: var(--text-3);
  text-transform: uppercase;
  letter-spacing: 0.06em;
}
.metric .v {
  font-size: 13px;
  color: var(--text-1);
}
.metric .v .num {
  color: var(--color-online);
  font-weight: 600;
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
