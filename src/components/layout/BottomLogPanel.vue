<template>
  <div class="bottom-log">
    <!-- 左栏：上位机日志 -->
    <div class="panel left-panel">
      <div class="header">
        <div class="title">
          <el-icon><Document /></el-icon>
          <span>上位机日志</span>
          <span class="count">最近 {{ recent.length }} 条</span>
        </div>
        <div class="legend">
          <span class="dot op" />操作
          <span class="dot comm" />通信
          <span class="dot warn" />报警
          <span class="dot sys" />系统
        </div>
      </div>
      <div class="list">
        <div v-if="!recent.length" class="empty">暂无日志</div>
        <div
          v-for="entry in recent"
          :key="entry.id"
          class="row"
          :class="['type-' + typeClass(entry.type)]"
        >
          <span class="time mono">{{ fmtTime(entry.time) }}</span>
          <span class="type" :class="'type-' + typeClass(entry.type)">{{ entry.type }}</span>
          <span class="rid mono">{{ entry.robotId ?? '----' }}</span>
          <span class="content">{{ entry.content }}</span>
        </div>
      </div>
    </div>

    <div class="divider" />

    <!-- 右栏：智能体遥测 -->
    <div class="panel right-panel">
      <div class="header">
        <div class="title">
          <el-icon><Cpu /></el-icon>
          <span>智能体遥测</span>
          <span v-if="selectedRobot" class="count">{{ selectedRobot }}</span>
        </div>
      </div>
      <div ref="telemetryListRef" class="list">
        <div v-if="!selectedRobot" class="empty">未选中设备</div>
        <div v-else-if="!telemetryEntries.length" class="empty">{{ telemetryEmptyText }}</div>
        <div
          v-for="msg in telemetryEntries"
          :key="msg.id"
          class="row telem-row"
        >
          <span class="time mono">{{ fmtTime(msg.time) }}</span>
          <span class="fields">
            <span v-for="(value, key) in msg.fields" :key="key" class="field">
              <span class="field-key">{{ key }}</span>
              <span class="field-val">{{ value }}</span>
            </span>
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import { Document, Cpu } from '@element-plus/icons-vue'
import { useLogsStore } from '@/stores/logs'
import { useRobotsStore } from '@/stores/robots'
import type { LogType } from '@/types'
import { useSystemStore } from '@/stores/system'
import { hasUsableDataChannel } from '@/utils/connection'

const logs = useLogsStore()
const robots = useRobotsStore()
const system = useSystemStore()
const recent = computed(() => logs.recent)
const selectedRobot = computed(() => robots.selectedId)

const telemetryEntries = computed(() => {
  if (!selectedRobot.value || !system.backendConnected || !hasUsableDataChannel(robots.selected)) return []
  return logs.getTelemetry(selectedRobot.value)
})
const telemetryEmptyText = computed(() => {
  if (!system.backendConnected) return '后端连接中断，遥测状态未知'
  if (!hasUsableDataChannel(robots.selected)) return '设备未连接或数据通道不可用'
  return '等待遥测数据...'
})

const telemetryListRef = ref<HTMLElement | null>(null)

// 新消息到来时自动滚动到底部
watch(telemetryEntries, () => {
  nextTick(() => {
    if (telemetryListRef.value) {
      telemetryListRef.value.scrollTop = telemetryListRef.value.scrollHeight
    }
  })
}, { deep: true })

function fmtTime(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
function typeClass(t: LogType): string {
  switch (t) {
    case '操作':
      return 'op'
    case '通信':
      return 'comm'
    case '报警':
      return 'warn'
    case '系统':
    default:
      return 'sys'
  }
}
</script>

<style scoped>
.bottom-log {
  height: 100%;
  display: flex;
  gap: 0;
}
.panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.left-panel {
  flex: 3;
}
.right-panel {
  flex: 2;
}
.divider {
  width: 1px;
  background: var(--border);
  flex-shrink: 0;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-app);
  font-size: 12px;
}
.title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-2);
  font-weight: 600;
  letter-spacing: 0.05em;
}
.count {
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 6px;
  font-size: 11px;
}
.legend {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--text-3);
  font-size: 11.5px;
}
.legend .dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 4px;
  vertical-align: middle;
}
.legend .op { background: var(--color-accent); }
.legend .comm { background: var(--color-info); }
.legend .warn { background: var(--color-warn); }
.legend .sys { background: var(--text-muted); }

.list {
  flex: 1;
  overflow: auto;
  padding: 4px 8px;
  font-family: 'JetBrains Mono', 'Consolas', 'Menlo', monospace;
  font-size: 12px;
  color: var(--text-2);
}
.empty {
  display: grid;
  place-items: center;
  height: 100%;
  color: var(--text-muted);
  font-family: inherit;
}

/* 日志行 */
.row {
  display: grid;
  grid-template-columns: 80px 56px 90px 1fr;
  gap: 8px;
  padding: 3px 6px;
  border-radius: 3px;
  align-items: baseline;
}
.row:hover {
  background: var(--bg-hover);
}
.row .time {
  color: var(--text-muted);
}
.row .rid {
  color: var(--text-3);
}
.row .content {
  color: var(--text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row .type {
  font-weight: 600;
  text-align: center;
  padding: 0 4px;
  border-radius: 3px;
  font-family: 'Inter', system-ui;
}
.row .type.type-op { color: var(--color-accent); background: rgba(59, 130, 246, 0.12); }
.row .type.type-comm { color: var(--color-info); background: rgba(96, 165, 250, 0.12); }
.row .type.type-warn { color: var(--color-warn); background: rgba(245, 158, 11, 0.14); }
.row .type.type-sys { color: var(--text-3); background: rgba(140, 140, 140, 0.12); }
.row.type-warn { background: rgba(245, 158, 11, 0.04); }

/* 遥测行 */
.telem-row {
  grid-template-columns: 80px 1fr;
  gap: 10px;
}
.telem-row .fields {
  display: flex;
  gap: 14px;
  flex-wrap: nowrap;
  white-space: nowrap;
  overflow: hidden;
}
.field {
  display: inline-flex;
  gap: 4px;
}
.field-key {
  color: var(--text-3);
  font-size: 11px;
}
.field-val {
  color: var(--text-1);
  font-weight: 500;
}
</style>
