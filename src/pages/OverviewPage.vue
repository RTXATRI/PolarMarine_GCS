<template>
  <div class="overview-page">
    <section class="kpi-bar" aria-label="设备概览指标">
      <article class="kpi">
        <span>设备总数</span><b>{{ fleet.devices.length }}</b>
      </article>
      <article class="kpi">
        <span>在线</span
        ><b class="online">{{ fleet.backendConnected ? fleet.onlineCount : '--' }}</b>
      </article>
      <article class="kpi">
        <span>离线</span
        ><b class="offline">{{
          fleet.backendConnected ? fleet.devices.length - fleet.onlineCount : '--'
        }}</b>
      </article>
      <article class="kpi">
        <span>报警中</span
        ><b class="warn">{{ fleet.backendConnected ? events.activeAlarms.length : '--' }}</b>
      </article>
      <article class="kpi">
        <span>自动模式</span><b>{{ fleet.backendConnected ? automaticCount : '--' }}</b>
      </article>
      <article class="kpi">
        <span>平均链路延迟</span>
        <b class="mono"
          >{{ fleet.backendConnected ? averageLatency : '--'
          }}<i v-if="fleet.backendConnected && averageLatency !== '--'">ms</i></b
        >
      </article>
    </section>

    <div class="content-row">
      <aside class="device-roster" aria-label="设备名册">
        <DeviceCard
          v-for="device in sortedDevices"
          :key="device.id"
          :device="device"
          :selected="device.id === fleet.selectedDeviceId"
          @select="fleet.selectDevice"
        />
      </aside>
      <section class="device-area">
        <QuickConnectionArea />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import DeviceCard from '@/entities/device/DeviceCard.vue'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import QuickConnectionArea from '@/features/links/QuickConnectionArea.vue'

const fleet = useFleetStore()
const events = useEventsStore()
const sortedDevices = computed(() =>
  [...fleet.devices].sort((left, right) => {
    const leftOnline = ['online', 'degraded'].includes(
      fleet.operationsByDeviceId[left.id]?.status ?? 'offline'
    )
      ? 0
      : 1
    const rightOnline = ['online', 'degraded'].includes(
      fleet.operationsByDeviceId[right.id]?.status ?? 'offline'
    )
      ? 0
      : 1
    return leftOnline - rightOnline || left.displayName.localeCompare(right.displayName, 'zh-CN')
  })
)
const automaticCount = computed(
  () =>
    fleet.devices.filter((device) => {
      const operation = fleet.operationsByDeviceId[device.id]
      if (!operation || !['online', 'degraded'].includes(operation.status)) return false
      const mode = fleet.telemetryByDeviceId[device.id]?.fields['control.mode']
      if (!mode || ['invalid', 'unknown', 'stale'].includes(mode.quality)) return false
      return (
        String(mode.value).toLocaleLowerCase().includes('auto') ||
        String(mode.value).includes('自动')
      )
    }).length
)
const averageLatency = computed<number | '--'>(() => {
  const latencies = Object.values(fleet.sessionsByLinkId).flatMap((session) =>
    session.state === 'healthy' && session.latencyMs != null ? [session.latencyMs] : []
  )
  return latencies.length
    ? Math.round(latencies.reduce((sum, latency) => sum + latency, 0) / latencies.length)
    : '--'
})
</script>

<style scoped>
.overview-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.kpi-bar {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 12px;
  flex: 0 0 auto;
}

.kpi {
  min-width: 0;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
}

.kpi span {
  display: block;
  overflow: hidden;
  color: var(--text-3);
  font-size: 11.5px;
  letter-spacing: 0.04em;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.kpi b {
  display: block;
  margin-top: 4px;
  color: var(--text-1);
  font-size: 22px;
}

.kpi b.online {
  color: var(--color-online);
}

.kpi b.offline {
  color: var(--color-offline);
}

.kpi b.warn {
  color: var(--color-warn);
}

.kpi i {
  margin-left: 4px;
  color: var(--text-3);
  font-size: 12px;
  font-style: normal;
  font-weight: 500;
}

.content-row {
  display: flex;
  flex: 1;
  gap: 12px;
  min-height: 0;
}

.device-roster {
  display: flex;
  flex: 0 0 370px;
  flex-direction: column;
  gap: 10px;
  padding-right: 10px;
  overflow-y: auto;
}

.device-area {
  flex: 1;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel);
}

@media (width <= 1450px) {
  .kpi-bar {
    gap: 8px;
  }

  .kpi {
    padding-inline: 10px;
  }

  .device-roster {
    flex-basis: 340px;
  }
}
</style>
