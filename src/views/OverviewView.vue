<template>
  <div class="overview">
    <div class="kpi-bar">
      <div class="kpi">
        <div class="kpi-label">设备总数</div>
        <div class="kpi-value">{{ total }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">在线</div>
        <div class="kpi-value online">{{ system.backendConnected ? onlineCount : '--' }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">离线</div>
        <div class="kpi-value offline">{{ system.backendConnected ? total - onlineCount : '--' }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">报警中</div>
        <div class="kpi-value warn">{{ system.backendConnected ? alarmCount : '--' }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">自动模式</div>
        <div class="kpi-value">{{ system.backendConnected ? autoCount : '--' }}</div>
      </div>
      <div class="kpi">
        <div class="kpi-label">平均链路延迟</div>
        <div class="kpi-value mono">
          {{ system.backendConnected ? avgLatency : '--' }}<span v-if="system.backendConnected && avgLatency !== '--'" class="unit">ms</span>
        </div>
      </div>
    </div>

    <div class="content-row">
      <div class="grid">
        <RobotCard
          v-for="r in robots.sortedRobots"
          :key="r.id"
          :robot="r"
          :is-selected="r.id === robots.selectedId"
          @select="onSelect"
        />
      </div>
      <div class="video-area">
        <DeviceConnectionArea :robot="robots.selected" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import RobotCard from '@/components/overview/RobotCard.vue'
import DeviceConnectionArea from '@/components/connection/DeviceConnectionArea.vue'
import { useRobotsStore } from '@/stores/robots'
import { useLogsStore } from '@/stores/logs'
import { useSystemStore } from '@/stores/system'

const robots = useRobotsStore()
const logs = useLogsStore()
const system = useSystemStore()

const total = computed(() => robots.robots.length)
const onlineCount = computed(() => robots.onlineCount)
const alarmCount = computed(() => robots.robots.filter(r => r.alarm).length)
const autoCount = computed(() => robots.robots.filter(r => r.mode === '自动').length)
const avgLatency = computed(() => {
  const arr = robots.robots.map(r => r.latencyMs).filter((v): v is number => v != null)
  if (!arr.length) return '--'
  return Math.round(arr.reduce((a, b) => a + b, 0) / arr.length)
})

function onSelect(id: string) {
  if (robots.select(id)) {
    logs.append('操作', id, `已切换当前设备为 ${id}`)
  }
}
</script>

<style scoped>
.overview {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.kpi-bar {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: 12px;
}
.kpi {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
}
.kpi-label {
  font-size: 11.5px;
  color: var(--text-3);
  letter-spacing: 0.04em;
}
.kpi-value {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-1);
  margin-top: 4px;
}
.kpi-value.online {
  color: var(--color-online);
}
.kpi-value.offline {
  color: var(--color-offline);
}
.kpi-value.warn {
  color: var(--color-warn);
}
.kpi-value .unit {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-3);
  margin-left: 4px;
}

.content-row {
  display: flex;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
  width: 370px;
  padding-right: 10px;
  flex-shrink: 0;
  overflow-y: auto;
}
.video-area {
  flex: 1;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  min-height: 0;
  overflow: hidden;
}
</style>
