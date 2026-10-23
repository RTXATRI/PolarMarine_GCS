<template>
  <div class="bottom-panel">
    <section class="panel log-panel">
      <div class="header">
        <div class="title">
          <el-icon><Document /></el-icon>
          <span>上位机日志</span>
          <span class="count">最近 {{ recentEvents.length }} 条</span>
        </div>
        <div class="legend">
          <span><i class="dot operation" />操作</span>
          <span><i class="dot communication" />通信</span>
          <span><i class="dot warning" />报警</span>
          <span><i class="dot system" />系统</span>
          <router-link to="/logs">查看全部</router-link>
        </div>
      </div>
      <div class="list">
        <div v-if="!recentEvents.length" class="empty">事件数据库暂无记录</div>
        <div v-for="event in recentEvents" :key="event.eventId" class="row log-row">
          <time class="mono">{{ shortTime(event.occurredAt) }}</time>
          <span class="event-type" :class="eventCategory(event.type)">
            {{ categoryLabel(event.type) }}
          </span>
          <span class="aggregate mono">{{ event.aggregateId }}</span>
          <span class="content">{{ eventText(event.type, event.payload) }}</span>
        </div>
      </div>
    </section>

    <div class="divider" />

    <section class="panel telemetry-panel">
      <div class="header">
        <div class="title">
          <el-icon><Cpu /></el-icon>
          <span>智能体遥测</span>
          <span v-if="fleet.selectedDevice" class="count">{{
            fleet.selectedDevice.displayName
          }}</span>
        </div>
      </div>
      <div class="list">
        <div v-if="!fleet.selectedDevice" class="empty">未选中设备</div>
        <div v-else-if="!fleet.backendConnected" class="empty">
          核心服务已断开，运行态遥测缓存已清空
        </div>
        <div v-else-if="!telemetrySamples.length" class="empty">尚无可信遥测采样</div>
        <div v-for="sample in telemetrySamples" :key="sample.id" class="row telemetry-row">
          <time class="mono">{{ shortTime(sample.sampledAt) }}</time>
          <div class="fields">
            <span
              ><i>电量</i><b>{{ fieldText(sample.fields['battery.percent']) }}</b></span
            >
            <span
              ><i>速度</i><b>{{ fieldText(sample.fields.speed) }}</b></span
            >
            <span
              ><i>航向</i><b>{{ fieldText(sample.fields.heading) }}</b></span
            >
            <span
              ><i>延迟</i
              ><b>{{
                sample.latencyMs == null ? '--' : `${sample.latencyMs.toFixed(0)} ms`
              }}</b></span
            >
            <span
              ><i>模式</i><b>{{ fieldText(sample.fields['control.mode']) }}</b></span
            >
          </div>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Cpu, Document } from '@element-plus/icons-vue'
import type { TelemetryValue } from '@/entities/types'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import { useTelemetryPresentationStore } from '@/entities/telemetry/presentation-store'
import { formatTelemetry } from '@/shared/lib/presentation'

const events = useEventsStore()
const fleet = useFleetStore()
const telemetry = useTelemetryPresentationStore()
const recentEvents = computed(() => events.events.slice(0, 12))
const telemetrySamples = computed(() =>
  [...telemetry.samplesFor(fleet.selectedDeviceId)].reverse().slice(0, 10)
)

function shortTime(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '--:--:--'
    : date.toLocaleTimeString('zh-CN', { hour12: false })
}

function eventCategory(type: string): 'operation' | 'communication' | 'warning' | 'system' {
  if (type.startsWith('alarm.')) return 'warning'
  if (type.startsWith('link_') || type.startsWith('telemetry.') || type.includes('route'))
    return 'communication'
  if (type.startsWith('command.') || type.startsWith('mission_') || type.startsWith('parameters.'))
    return 'operation'
  return 'system'
}

function categoryLabel(type: string): string {
  const labels = {
    operation: '操作',
    communication: '通信',
    warning: '报警',
    system: '系统'
  }
  return labels[eventCategory(type)]
}

function eventText(type: string, payload: Record<string, unknown>): string {
  const meaningful = Object.entries(payload)
    .filter(([key]) => !['schemaVersion', 'deviceId', 'updatedAt'].includes(key))
    .slice(0, 3)
    .map(([key, value]) => `${key}=${scalar(value)}`)
    .join(' · ')
  return `${type}${meaningful ? ` · ${meaningful}` : ''}`
}

function scalar(value: unknown): string {
  if (value == null) return '--'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function fieldText(value: TelemetryValue | undefined): string {
  return value ? formatTelemetry(value) : '--'
}
</script>

<style scoped>
.bottom-panel {
  display: grid;
  grid-template-columns: minmax(0, 3fr) 1px minmax(0, 2fr);
  height: 100%;
}

.panel {
  display: flex;
  flex-direction: column;
  min-width: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
}

.divider {
  background: var(--border);
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 31px;
  height: 31px;
  padding: 0 10px;
  border-bottom: 1px solid var(--border);
}

.title,
.legend,
.legend span {
  display: flex;
  align-items: center;
}

.title {
  gap: 6px;
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
}

.count {
  margin-left: 4px;
  color: var(--text-muted);
  font-size: 10px;
  font-weight: 400;
}

.legend {
  gap: 10px;
  color: var(--text-3);
  font-size: 10px;
}

.legend span {
  gap: 4px;
}

.legend a {
  margin-left: 4px;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}

.dot.operation {
  background: var(--color-accent);
}

.dot.communication {
  background: var(--color-info);
}

.dot.warning {
  background: var(--color-warn);
}

.dot.system {
  background: var(--text-muted);
}

.list {
  flex: 1;
  min-height: 0;
  padding: 4px 6px;
  overflow: auto;
}

.row {
  align-items: baseline;
  min-height: 21px;
  padding: 3px 6px;
  border-radius: 3px;
  font-size: 10.5px;
}

.row:hover {
  background: var(--bg-hover);
}

.log-row {
  display: grid;
  grid-template-columns: 74px 42px 112px minmax(0, 1fr);
  gap: 8px;
}

time,
.aggregate {
  overflow: hidden;
  color: var(--text-muted);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.event-type {
  border-radius: 3px;
  text-align: center;
}

.event-type.operation {
  color: var(--color-accent);
  background: rgb(59 130 246 / 12%);
}

.event-type.communication {
  color: var(--color-info);
  background: rgb(96 165 250 / 12%);
}

.event-type.warning {
  color: var(--color-warn);
  background: rgb(245 158 11 / 14%);
}

.event-type.system {
  color: var(--text-3);
  background: rgb(140 140 140 / 12%);
}

.content {
  overflow: hidden;
  color: var(--text-1);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.telemetry-row {
  display: grid;
  grid-template-columns: 74px minmax(0, 1fr);
  gap: 10px;
}

.fields {
  display: flex;
  gap: 13px;
  overflow: hidden;
  white-space: nowrap;
}

.fields span {
  display: inline-flex;
  gap: 4px;
}

.fields i {
  color: var(--text-3);
  font-size: 10px;
  font-style: normal;
}

.fields b {
  color: var(--text-1);
  font-weight: 500;
}

.empty {
  display: grid;
  height: 100%;
  place-items: center;
  color: var(--text-muted);
  font-size: 11px;
}
</style>
