<template>
  <div class="right-panel">
    <div class="header">
      <div class="title">
        <el-icon><Aim /></el-icon>
        <span>设备状态</span>
      </div>
      <div v-if="r" class="badge">
        <StatusDot :tone="statusTone" :label="statusText" />
      </div>
    </div>

    <div v-if="!r" class="empty">未选中设备</div>

    <div v-else class="body">
      <div class="card">
        <div class="row big">
          <span class="rid">{{ r.id }}</span>
          <span class="link tag-pill" :class="connected ? 'info' : 'offline'">{{ connected ? connectionMethodText(r) : '未知' }}</span>
        </div>
        <div class="kv-row">
          <span class="k">在线状态</span>
          <span class="v">
            <StatusDot :tone="statusTone" :label="statusText" />
          </span>
        </div>
        <div class="kv-row">
          <span class="k">连接方式</span>
          <span class="v">{{ connected ? connectionMethodText(r) : '未知' }}</span>
        </div>
        <div class="kv-row">
          <span class="k">控制模式</span>
          <span class="v">
            <span class="tag-pill" :class="modeTone">{{ !connected ? '未知' : (r.robotType === 'dock' ? '固定' : (r.mode ?? '未知')) }}</span>
          </span>
        </div>
        <div v-if="r.robotType !== 'dock'" class="kv-row">
          <span class="k">PX4 模式</span>
          <span class="v mono">{{ connected ? (r.px4Mode ?? '--') : '--' }}</span>
        </div>
        <div class="kv-row">
          <span class="k">任务状态</span>
          <span class="v">{{ connected ? (r.missionStatus ?? '未知') : '未知' }}</span>
        </div>
        <div class="kv-row">
          <span class="k">报警</span>
          <span class="v">
            <span v-if="!system.backendConnected" class="muted">未知</span>
            <span v-else-if="r.alarm" class="tag-pill warn">{{ r.alarm }}</span>
            <span v-else class="muted">无</span>
          </span>
        </div>
      </div>

      <div class="card">
        <div class="section-title">数据</div>
        <div class="kv-row">
          <span class="k">电池</span>
          <span class="v">{{ formatBattery(connected ? r.battery : null) }}</span>
        </div>
        <div v-if="r.robotType !== 'dock'" class="kv-row">
          <span class="k">速度</span>
          <span class="v">{{ formatNum(connected ? r.speed : null, 'm/s', 2) }}</span>
        </div>
        <div v-if="r.robotType !== 'dock'" class="kv-row">
          <span class="k">航向</span>
          <span class="v">{{ formatNum(connected ? r.heading : null, '°', 0) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">位置</span>
          <span class="v">{{ formatPos(connected ? r.position : null) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">海拔</span>
          <span class="v">{{ formatNum(connected ? r.altitude : null, 'm', 1) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">链路状态</span>
          <span class="v">
            <span class="tag-pill" :class="linkTone">{{ connected ? (r.linkStatus ?? '未知') : '未知' }}</span>
          </span>
        </div>
        <div class="kv-row">
          <span class="k">延迟</span>
          <span class="v">{{ formatNum(connected ? r.latencyMs : null, 'ms', 0) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">丢包</span>
          <span class="v">{{ formatNum(connected ? r.packetLoss : null, '%', 1) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">RSSI</span>
          <span class="v">{{ formatNum(connected ? r.rssi : null, 'dBm', 0) }}</span>
        </div>
        <div class="kv-row">
          <span class="k">最后通信</span>
          <span class="v">{{ formatLastComm(system.backendConnected ? r.lastCommAt : null) }}</span>
        </div>
      </div>

      <div v-if="connected && system.backendConnected && r.robotType !== 'dock'" class="card">
        <div class="section-title">趋势 · 60s</div>
        <div class="trend-block">
          <div class="trend-label">
            <span>电池</span>
            <span class="mono">{{ formatBattery(r.battery) }}</span>
          </div>
          <TrendChart :data="trends.battery" :height="44" color="#2ecc71" :min="0" :max="100" unit="%" />
        </div>
        <div class="trend-block">
          <div class="trend-label">
            <span>延迟</span>
            <span class="mono">{{ formatNum(r.latencyMs, 'ms', 0) }}</span>
          </div>
          <TrendChart :data="trends.latency" :height="44" color="#f59e0b" unit="ms" />
        </div>
        <div class="trend-block">
          <div class="trend-label">
            <span>速度</span>
            <span class="mono">{{ formatNum(r.speed, 'm/s', 2) }}</span>
          </div>
          <TrendChart :data="trends.speed" :height="44" color="#3b82f6" :min="0" unit="m/s" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Aim } from '@element-plus/icons-vue'
import StatusDot from '@/components/common/StatusDot.vue'
import TrendChart from '@/components/common/TrendChart.vue'
import { useRobotsStore } from '@/stores/robots'
import { useTrendsStore } from '@/stores/trends'
import { useSystemStore } from '@/stores/system'
import { connectionMethodText, connectionStateText, connectionTone, isRobotConnected } from '@/utils/connection'

const robots = useRobotsStore()
const trendsStore = useTrendsStore()
const system = useSystemStore()

const r = computed(() => robots.selected)
const connected = computed(() => system.backendConnected && isRobotConnected(r.value))
const statusText = computed(() => {
  if (!system.backendConnected) return '状态未知'
  return r.value ? connectionStateText(r.value.connection.state) : '未选中'
})
const statusTone = computed(() => {
  if (!system.backendConnected || !r.value) return 'offline' as const
  return connectionTone(r.value.connection.state)
})
const trends = computed(() => (r.value ? trendsStore.get(r.value.id) : { battery: [], latency: [], speed: [] }))
const modeTone = computed(() => {
  if (!connected.value) return 'offline'
  switch (r.value?.mode) {
    case '手动':
      return 'info'
    case '自动':
      return 'online'
    case '急停':
      return 'danger'
    default:
      return 'offline'
  }
})
const linkTone = computed(() => {
  if (!connected.value) return 'offline'
  switch (r.value?.linkStatus) {
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

function formatBattery(v: number | null) {
  return v == null ? '未知' : `${v}%`
}
function formatNum(v: number | null, unit: string, digits: number) {
  if (v == null) return '--'
  return `${v.toFixed(digits)} ${unit}`
}
function formatPos(p: { lat: number; lon: number } | null) {
  if (!p) return '未知'
  return `${p.lat.toFixed(4)}, ${p.lon.toFixed(4)}`
}
function formatLastComm(iso: string | null) {
  if (!iso) return '--'
  const dt = new Date(iso).getTime()
  const diff = Math.max(0, Math.floor((system.now - dt) / 1000))
  if (diff < 60) return `${diff}s 前`
  if (diff < 3600) return `${Math.floor(diff / 60)}min 前`
  return `${Math.floor(diff / 3600)}h 前`
}
</script>

<style scoped>
.right-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 36px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-app);
}
.title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--text-2);
  letter-spacing: 0.06em;
}
.empty {
  flex: 1;
  display: grid;
  place-items: center;
  color: var(--text-muted);
  font-size: 13px;
}
.body {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 12px;
}
.row.big {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}
.rid {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-1);
  font-family: 'JetBrains Mono', 'Consolas', monospace;
}
.trend-block + .trend-block {
  margin-top: 8px;
}
.trend-label {
  display: flex;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--text-3);
  padding-bottom: 2px;
}
</style>
