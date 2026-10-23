<template>
  <div class="top-bar">
    <div class="brand">
      <div class="logo" aria-hidden="true">
        <svg viewBox="0 0 64 64" width="22" height="22">
          <circle cx="32" cy="32" r="18" fill="none" stroke="currentColor" stroke-width="3" />
          <circle cx="32" cy="32" r="5" fill="currentColor" />
          <path
            d="M32 8v8m0 32v8M8 32h8m32 0h8"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
          />
        </svg>
      </div>
      <div class="brand-text">
        <div class="title">PolarMarine GCS <span class="beta-tag">Beta</span></div>
        <div class="subtitle">Ground Control Station</div>
      </div>
    </div>

    <div class="metrics">
      <div class="metric">
        <span class="key">系统状态</span>
        <StatusDot :tone="systemTone" :label="systemLabel" />
      </div>
      <div class="metric">
        <span class="key">当前时间</span>
        <span class="value mono">{{ clock }}</span>
      </div>
      <div class="metric">
        <span class="key">已连接设备</span>
        <span class="value mono"
          ><b class="online-number">{{ fleet.backendConnected ? fleet.onlineCount : '--' }}</b>
          <span class="muted"> / {{ fleet.devices.length }}</span></span
        >
      </div>
      <div class="metric">
        <span class="key">当前设备</span>
        <span class="value mono device-id">{{ fleet.selectedDevice?.id ?? '--' }}</span>
      </div>
      <div class="metric">
        <span class="key">控制模式</span>
        <span class="tag-pill" :class="modeTone">{{ modeText }}</span>
      </div>
      <div class="metric">
        <span class="key">链路</span>
        <span class="tag-pill" :class="linkTone">
          {{ linkText }}<span v-if="linkLatency" class="latency">{{ linkLatency }}</span>
        </span>
      </div>
    </div>

    <div class="actions">
      <el-tooltip :content="theme.theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'">
        <el-button circle size="small" aria-label="切换主题" @click="theme.toggle()">
          <el-icon v-if="theme.theme === 'dark'"><Sunny /></el-icon>
          <el-icon v-else><Moon /></el-icon>
        </el-button>
      </el-tooltip>
      <EmergencyButton compact />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { Moon, Sunny } from '@element-plus/icons-vue'
import { useApplicationStore } from '@/app/store'
import { useThemeStore } from '@/app/theme-store'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import EmergencyButton from '@/features/commands/EmergencyButton.vue'
import { driverLabel } from '@/shared/lib/presentation'
import StatusDot from '@/shared/ui/StatusDot.vue'

const application = useApplicationStore()
const theme = useThemeStore()
const events = useEventsStore()
const fleet = useFleetStore()
const clock = ref('')

const updateClock = (): void => {
  clock.value = new Date().toLocaleString('zh-CN', { hour12: false })
}
updateClock()
const timer = window.setInterval(updateClock, 1_000)
onBeforeUnmount(() => window.clearInterval(timer))

const systemTone = computed<'online' | 'warn' | 'danger'>(() => {
  if (application.streamState !== 'connected') return 'danger'
  if (events.activeAlarms.length > 0 || fleet.selectedOperationalState?.status === 'degraded')
    return 'warn'
  return 'online'
})

const systemLabel = computed(() => {
  if (application.streamState === 'connecting') return '核心连接中'
  if (application.streamState !== 'connected') return '核心已断开'
  if (fleet.devices.length > 0 && fleet.onlineCount === 0) return '等待设备连接'
  if (systemTone.value === 'warn') return '部分异常'
  return '系统正常'
})

const modeText = computed(() => {
  if (!fleet.backendConnected) return '未知'
  const field = fleet.selectedTelemetry?.fields['control.mode']
  if (!field || ['invalid', 'unknown', 'stale'].includes(field.quality)) return '未知'
  return typeof field.value === 'string' ? field.value : String(field.value ?? '未知')
})

const modeTone = computed(() => {
  const normalized = modeText.value.toLocaleLowerCase()
  if (normalized.includes('急停') || normalized.includes('emergency')) return 'danger'
  if (normalized.includes('自动') || normalized.includes('auto')) return 'online'
  if (normalized.includes('手动') || normalized.includes('manual')) return 'info'
  return 'offline'
})

const activeSession = computed(() => {
  const activeLinkId = fleet.selectedOperationalState?.activeLinkId
  return activeLinkId ? fleet.sessionsByLinkId[activeLinkId] : undefined
})

const activeProfile = computed(() => {
  const activeLinkId = fleet.selectedOperationalState?.activeLinkId
  return activeLinkId ? fleet.linksById[activeLinkId] : undefined
})

const linkText = computed(() => {
  if (!fleet.selectedOnline || !activeSession.value) return '断开'
  if (fleet.selectedOperationalState?.status === 'failing_over') return '切换中'
  if (fleet.selectedOperationalState?.status === 'degraded') return '降级'
  return activeProfile.value ? driverLabel(activeProfile.value.driver) : '正常'
})

const linkTone = computed(() => {
  if (!fleet.selectedOnline) return 'offline'
  return fleet.selectedOperationalState?.status === 'online' ? 'online' : 'warn'
})

const linkLatency = computed(() =>
  activeSession.value?.latencyMs == null ? '' : `${Math.round(activeSession.value.latencyMs)}ms`
)
</script>

<style scoped>
.top-bar {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) auto;
  align-items: center;
  gap: 16px;
  height: 100%;
  padding: 0 12px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.logo {
  display: grid;
  flex: 0 0 30px;
  place-items: center;
  width: 30px;
  height: 30px;
  color: #60a5fa;
  border-radius: 6px;
  background: rgb(96 165 250 / 12%);
}

.brand-text {
  min-width: 0;
}

.title {
  color: var(--text-1);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.04em;
  white-space: nowrap;
}

.subtitle {
  color: var(--text-3);
  font-size: 11px;
}

.beta-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 0 4px;
  color: #f59e0b;
  border: 1px solid rgb(245 158 11 / 40%);
  border-radius: 3px;
  background: rgb(245 158 11 / 12%);
  font-size: 9px;
  font-weight: 600;
  line-height: 16px;
  vertical-align: middle;
}

.metrics {
  display: flex;
  align-items: center;
  gap: clamp(10px, 1.25vw, 22px);
  min-width: 0;
  overflow: hidden;
}

.metric {
  display: flex;
  flex: 0 1 auto;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.key {
  color: var(--text-3);
  font-size: 10.5px;
  letter-spacing: 0.06em;
  white-space: nowrap;
}

.value {
  overflow: hidden;
  color: var(--text-1);
  font-size: 12.5px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-id {
  max-width: 124px;
}

.online-number {
  color: var(--color-online);
  font-weight: 600;
}

.latency {
  margin-left: 5px;
  color: var(--text-3);
}

.actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

@media (width <= 1450px) {
  .top-bar {
    grid-template-columns: 205px minmax(0, 1fr) auto;
    gap: 10px;
  }

  .metrics {
    gap: 10px;
  }

  .metric:nth-child(2) {
    display: none;
  }
}
</style>
