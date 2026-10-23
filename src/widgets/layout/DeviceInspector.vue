<template>
  <div class="device-inspector">
    <div class="header">
      <div class="title">
        <el-icon><Aim /></el-icon>
        <span>设备状态</span>
      </div>
      <StatusDot
        v-if="fleet.selectedDevice"
        :tone="operationTone(operation?.status)"
        :label="operationText(operation?.status)"
      />
    </div>

    <div v-if="!fleet.selectedDevice" class="empty">未选中设备</div>
    <div v-else class="body">
      <section class="card">
        <div class="identity">
          <span class="device-name">{{ fleet.selectedDevice.displayName }}</span>
          <span v-if="simulated" class="tag-pill simulation">仿真数据</span>
          <span v-else class="tag-pill" :class="fleet.selectedOnline ? 'info' : 'offline'">
            {{ activeProfile ? driverLabel(activeProfile.driver) : '无活动路由' }}
          </span>
        </div>
        <div class="kv-row">
          <span class="k">设备编号</span><span class="v">{{ fleet.selectedDevice.id }}</span>
        </div>
        <div class="kv-row">
          <span class="k">模板类型</span>
          <span class="v">{{ fleet.selectedTemplate?.displayName ?? '--' }}</span>
        </div>
        <div class="kv-row">
          <span class="k">在线状态</span>
          <span class="v"
            ><StatusDot
              :tone="operationTone(operation?.status)"
              :label="operationText(operation?.status)"
          /></span>
        </div>
        <div class="kv-row">
          <span class="k">控制模式</span>
          <span class="tag-pill" :class="modeTone">{{ modeText }}</span>
        </div>
        <div class="kv-row">
          <span class="k">任务状态</span><span class="v">{{ missionText }}</span>
        </div>
        <div class="kv-row">
          <span class="k">活动路由</span>
          <span class="v route-name">{{ activeProfile?.displayName ?? '--' }}</span>
        </div>
        <div class="kv-row">
          <span class="k">健康链路</span>
          <span class="v"
            >{{ operation?.healthyLinkIds.length ?? 0 }} / {{ fleet.selectedLinks.length }}</span
          >
        </div>
        <div class="kv-row">
          <span class="k">报警</span>
          <span v-if="selectedAlarms.length" class="tag-pill warn">
            {{ selectedAlarms[0]?.message }}
          </span>
          <span v-else class="v muted">无</span>
        </div>
      </section>

      <section class="card">
        <div class="section-title">数据</div>
        <div class="kv-row">
          <span class="k">电池</span>
          <span class="v">{{ valueText(telemetry, 'battery.percent', '未知') }}</span>
        </div>
        <div class="kv-row">
          <span class="k">速度</span>
          <span class="v">{{ valueText(telemetry, 'speed') }}</span>
        </div>
        <div class="kv-row">
          <span class="k">航向</span>
          <span class="v">{{ valueText(telemetry, 'heading') }}</span>
        </div>
        <div class="kv-row">
          <span class="k">位置</span>
          <span class="v">{{ positionText }}</span>
        </div>
        <div class="kv-row">
          <span class="k">海拔</span>
          <span class="v">{{ valueText(telemetry, 'position.altitude') }}</span>
        </div>
        <div class="kv-row">
          <span class="k">链路状态</span>
          <span class="tag-pill" :class="linkTone">{{ linkText }}</span>
        </div>
        <div class="kv-row">
          <span class="k">延迟</span>
          <span class="v">{{ formatNumber(activeSession?.latencyMs, 'ms', 0) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">丢包</span>
          <span class="v">{{ formatNumber(activeSession?.packetLossPercent, '%', 1) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">最后遥测</span>
          <span class="v">{{ lastTelemetryText }}</span>
        </div>
      </section>

      <section v-if="fleet.selectedOnline" class="card trend-card">
        <div class="section-title">趋势 · 60 秒</div>
        <div class="trend-block">
          <div class="trend-label">
            <span>电池</span><span class="mono">{{ valueText(telemetry, 'battery.percent') }}</span>
          </div>
          <TrendChart :data="trendData.battery" :height="42" color="#2ecc71" :min="0" :max="100" />
        </div>
        <div class="trend-block">
          <div class="trend-label">
            <span>延迟</span
            ><span class="mono">{{ formatNumber(activeSession?.latencyMs, 'ms', 0) }}</span>
          </div>
          <TrendChart :data="trendData.latency" :height="42" color="#f59e0b" :min="0" />
        </div>
        <div class="trend-block">
          <div class="trend-label">
            <span>速度</span><span class="mono">{{ valueText(telemetry, 'speed') }}</span>
          </div>
          <TrendChart :data="trendData.speed" :height="42" color="#3b82f6" :min="0" />
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Aim } from '@element-plus/icons-vue'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import { useTelemetryPresentationStore } from '@/entities/telemetry/presentation-store'
import {
  isSimulatorRoute,
  numericTelemetry,
  operationText,
  operationTone,
  valueText
} from '@/shared/lib/device-view'
import { driverLabel } from '@/shared/lib/presentation'
import StatusDot from '@/shared/ui/StatusDot.vue'
import TrendChart from '@/shared/ui/TrendChart.vue'

const fleet = useFleetStore()
const events = useEventsStore()
const history = useTelemetryPresentationStore()
const operation = computed(() => fleet.selectedOperationalState)
const telemetry = computed(() => fleet.selectedTelemetry)
const activeProfile = computed(() => {
  const linkId = operation.value?.activeLinkId
  return linkId ? fleet.linksById[linkId] : undefined
})
const activeSession = computed(() => {
  const linkId = operation.value?.activeLinkId
  return linkId ? fleet.sessionsByLinkId[linkId] : undefined
})
const simulated = computed(() => isSimulatorRoute(operation.value, fleet.linksById))
const selectedAlarms = computed(() =>
  events.activeAlarms.filter((alarm) => alarm.deviceId === fleet.selectedDeviceId)
)
const modeText = computed(() => valueText(telemetry.value, 'control.mode', '未知'))
const missionText = computed(() => valueText(telemetry.value, 'mission.status', '未知'))
const modeTone = computed(() => {
  const mode = modeText.value.toLocaleLowerCase()
  if (mode.includes('急停') || mode.includes('emergency')) return 'danger'
  if (mode.includes('自动') || mode.includes('auto')) return 'online'
  if (mode.includes('手动') || mode.includes('manual')) return 'info'
  return 'offline'
})
const linkText = computed(() => {
  if (!fleet.selectedOnline) return '断开'
  if (operation.value?.status === 'failing_over') return '切换中'
  if (operation.value?.status === 'degraded') return '降级'
  return '正常'
})
const linkTone = computed(() => (operation.value?.status === 'online' ? 'online' : 'warn'))
const positionText = computed(() => {
  const latitude = telemetry.value?.fields['position.latitude']
  const longitude = telemetry.value?.fields['position.longitude']
  if (latitude?.quality === 'stale' || longitude?.quality === 'stale') return '已过期'
  const lat = numericTelemetry(telemetry.value, 'position.latitude')
  const lon = numericTelemetry(telemetry.value, 'position.longitude')
  return lat == null || lon == null ? '无效' : `${lat.toFixed(4)}, ${lon.toFixed(4)}`
})
const lastTelemetryText = computed(() => {
  if (!telemetry.value?.updatedAt) return '--'
  const milliseconds = Date.now() - Date.parse(telemetry.value.updatedAt)
  if (!Number.isFinite(milliseconds)) return '--'
  const seconds = Math.max(0, Math.floor(milliseconds / 1_000))
  if (seconds < 60) return `${seconds}s 前`
  if (seconds < 3_600) return `${Math.floor(seconds / 60)}min 前`
  return `${Math.floor(seconds / 3_600)}h 前`
})
const trendData = computed(() => {
  const samples = history.samplesFor(fleet.selectedDeviceId)
  return {
    battery: samples.flatMap((sample) => numberFromSample(sample.fields['battery.percent'])),
    latency: samples.flatMap((sample) => (sample.latencyMs == null ? [] : [sample.latencyMs])),
    speed: samples.flatMap((sample) => numberFromSample(sample.fields.speed))
  }
})

function numberFromSample(field: { value: unknown; quality: string } | undefined): number[] {
  return field &&
    typeof field.value === 'number' &&
    Number.isFinite(field.value) &&
    !['invalid', 'unknown', 'stale'].includes(field.quality)
    ? [field.value]
    : []
}

function formatNumber(value: number | null | undefined, unit: string, digits: number): string {
  return value == null ? '--' : `${value.toFixed(digits)} ${unit}`
}
</script>

<style scoped>
.device-inspector {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 36px;
  height: 36px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border);
}

.title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-2);
  font-size: 12.5px;
  font-weight: 600;
  letter-spacing: 0.06em;
}

.empty {
  display: grid;
  flex: 1;
  place-items: center;
  color: var(--text-muted);
}

.body {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
  padding: 10px;
  overflow-y: auto;
}

.card {
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
}

.identity {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 7px;
}

.device-name {
  overflow: hidden;
  color: var(--text-1);
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 14px;
  font-weight: 700;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.route-name {
  max-width: 155px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.simulation {
  color: #c084fc;
  border-color: rgb(192 132 252 / 45%);
  background: rgb(192 132 252 / 12%);
}

.trend-block + .trend-block {
  margin-top: 7px;
}

.trend-label {
  display: flex;
  justify-content: space-between;
  padding-bottom: 1px;
  color: var(--text-3);
  font-size: 11px;
}
</style>
