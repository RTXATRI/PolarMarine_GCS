<template>
  <button
    class="device-card"
    :class="{
      selected,
      offline: operation.status === 'offline',
      alarming: selectedAlarms.length > 0
    }"
    type="button"
    @click="$emit('select', device.id)"
  >
    <span class="card-header">
      <span class="identity">
        <span class="name-line">
          <b class="device-name">{{ device.displayName }}</b>
          <span class="tag-pill" :class="categoryTone">{{
            categoryLabel(template?.category)
          }}</span>
          <StatusDot
            :tone="operationTone(operation.status)"
            :label="operationText(operation.status)"
          />
          <span v-if="simulated" class="tag-pill simulation">仿真</span>
        </span>
        <span class="device-id mono">{{ device.id }}</span>
      </span>
      <span class="tag-pill" :class="fleet.backendConnected && activeProfile ? 'info' : 'offline'">
        {{ fleet.backendConnected && activeProfile ? driverLabel(activeProfile.driver) : '未知' }}
      </span>
    </span>

    <span class="card-body">
      <span class="kv-row">
        <span class="k">电池</span>
        <span class="v">
          <template v-if="battery != null">
            <span class="battery-bar"
              ><span
                class="battery-fill"
                :class="batteryClass"
                :style="{ width: `${Math.max(0, Math.min(100, battery))}%` }"
            /></span>
            <span class="mono">{{ Math.round(battery) }}%</span>
          </template>
          <span v-else class="muted">{{ valueText(telemetry, 'battery.percent', '未知') }}</span>
        </span>
      </span>
      <span class="kv-row">
        <span class="k">控制模式</span>
        <span class="tag-pill" :class="modeTone">{{ modeText }}</span>
      </span>
      <span class="kv-row">
        <span class="k">任务状态</span>
        <span class="v">{{ valueText(telemetry, 'mission.status', '未知') }}</span>
      </span>
      <span class="kv-row">
        <span class="k">链路</span>
        <span class="v">
          <span class="tag-pill" :class="linkTone">{{ linkText }}</span>
          <span v-if="activeSession?.latencyMs != null" class="latency mono">
            {{ Math.round(activeSession.latencyMs) }}ms
          </span>
        </span>
      </span>
      <span class="kv-row">
        <span class="k">报警</span>
        <span v-if="selectedAlarms.length" class="tag-pill warn alarm-text">
          {{ selectedAlarms[0]?.message }}
        </span>
        <span v-else class="v muted">无</span>
      </span>
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Device } from '@/entities/types'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import {
  categoryLabel,
  isSimulatorRoute,
  numericTelemetry,
  operationText,
  operationTone,
  valueText
} from '@/shared/lib/device-view'
import { driverLabel } from '@/shared/lib/presentation'
import StatusDot from '@/shared/ui/StatusDot.vue'

const props = defineProps<{ device: Device; selected: boolean }>()
defineEmits<{ select: [deviceId: string] }>()

const fleet = useFleetStore()
const events = useEventsStore()
const template = computed(() => fleet.templatesById[props.device.templateId])
const operation = computed(
  () =>
    fleet.operationsByDeviceId[props.device.id] ?? {
      deviceId: props.device.id,
      status: 'offline' as const,
      activeLinkId: null,
      healthyLinkIds: [],
      lastFailoverAt: null,
      revision: 0
    }
)
const telemetry = computed(() => fleet.telemetryByDeviceId[props.device.id])
const activeProfile = computed(() => {
  const linkId = operation.value.activeLinkId
  return linkId ? fleet.linksById[linkId] : undefined
})
const activeSession = computed(() => {
  const linkId = operation.value.activeLinkId
  return linkId ? fleet.sessionsByLinkId[linkId] : undefined
})
const selectedAlarms = computed(() =>
  events.activeAlarms.filter((alarm) => alarm.deviceId === props.device.id)
)
const simulated = computed(() => isSimulatorRoute(operation.value, fleet.linksById))
const battery = computed(() => numericTelemetry(telemetry.value, 'battery.percent'))
const batteryClass = computed(() =>
  battery.value == null ? '' : battery.value <= 20 ? 'critical' : battery.value <= 40 ? 'low' : 'ok'
)
const modeText = computed(() =>
  operation.value.status === 'offline' ? '未知' : valueText(telemetry.value, 'control.mode', '未知')
)
const modeTone = computed(() => {
  const mode = modeText.value.toLocaleLowerCase()
  if (mode.includes('急停') || mode.includes('emergency')) return 'danger'
  if (mode.includes('自动') || mode.includes('auto')) return 'online'
  if (mode.includes('手动') || mode.includes('manual')) return 'info'
  return 'offline'
})
const linkText = computed(() => {
  if (operation.value.status === 'offline') return '断开'
  if (operation.value.status === 'degraded') return '降级'
  if (operation.value.status === 'failing_over') return '切换中'
  return '正常'
})
const linkTone = computed(() => (operation.value.status === 'online' ? 'online' : 'warn'))
const categoryTone = computed(() => {
  if (template.value?.category === 'aerial') return 'info'
  if (template.value?.category === 'surface') return 'online'
  if (template.value?.category === 'station') return 'warn'
  return 'offline'
})
</script>

<style scoped>
.device-card {
  position: relative;
  display: block;
  width: 100%;
  padding: 12px 14px;
  color: var(--text-1);
  text-align: left;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
  cursor: pointer;
  transition:
    border-color 150ms ease,
    box-shadow 150ms ease,
    background 150ms ease;
}

.device-card:hover {
  border-color: var(--border-strong);
  background: var(--bg-panel-2);
}

.device-card.selected {
  border-color: var(--color-accent);
  background: rgb(59 130 246 / 9%);
  box-shadow:
    0 0 0 1px var(--color-accent),
    0 0 14px rgb(59 130 246 / 20%);
}

.device-card.offline {
  opacity: 0.85;
}

.device-card.alarming::before {
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  border-radius: var(--radius-md) var(--radius-md) 0 0;
  background: linear-gradient(90deg, var(--color-warn), transparent);
  content: '';
}

.card-header,
.name-line,
.kv-row {
  display: flex;
  align-items: center;
}

.card-header {
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 8px;
}

.identity {
  min-width: 0;
}

.name-line {
  gap: 8px;
  min-width: 0;
}

.device-name {
  overflow: hidden;
  max-width: 116px;
  color: var(--text-1);
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-id {
  display: block;
  margin-top: 2px;
  color: var(--text-3);
  font-size: 10px;
}

.card-body {
  display: block;
}

.kv-row {
  min-height: 25px;
}

.kv-row .v {
  display: inline-flex;
  align-items: center;
}

.battery-bar {
  position: relative;
  display: inline-block;
  width: 60px;
  height: 6px;
  margin-right: 6px;
  overflow: hidden;
  vertical-align: middle;
  border: 1px solid var(--border);
  border-radius: 3px;
  background: var(--bg-panel-2);
}

.battery-fill {
  display: block;
  height: 100%;
  border-radius: 2px;
}

.battery-fill.ok {
  background: var(--color-online);
}

.battery-fill.low {
  background: var(--color-warn);
}

.battery-fill.critical {
  background: var(--color-danger);
}

.latency {
  margin-left: 6px;
  color: var(--text-3);
}

.alarm-text {
  max-width: 190px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.simulation {
  color: #c084fc;
  border-color: rgb(192 132 252 / 45%);
  background: rgb(192 132 252 / 12%);
}
</style>
