<template>
  <div class="card" :class="{ selected: isSelected, offline: !connected, alarming: system.backendConnected && !!robot.alarm }" @click="onClick">
    <div class="card-header">
      <div class="id-line">
        <span class="id mono">{{ robot.id }}</span>
        <span class="type-tag tag-pill" :class="typeTone">{{ typeLabel }}</span>
        <StatusDot :tone="stateTone" :label="stateText" />
        <span v-if="isSelected" class="select-flag">
          <el-icon><Aim /></el-icon>
          当前选中
        </span>
      </div>
      <span class="link-tag tag-pill" :class="connected ? 'info' : 'offline'">{{ methodText }}</span>
    </div>

    <div class="card-body">
      <div class="kv-row">
        <span class="k">电池</span>
        <span class="v">
          <template v-if="connected && robot.battery !== null">
            <span class="battery-bar">
              <span class="bar-fill" :class="batteryClass" :style="{ width: robot.battery + '%' }" />
            </span>
            <span class="mono">{{ robot.battery }}%</span>
          </template>
          <span v-else class="muted">未知</span>
        </span>
      </div>
      <div class="kv-row">
        <span class="k">控制模式</span>
        <span class="v">
          <span class="tag-pill" :class="modeTone">{{ connected ? (robot.mode ?? '未知') : '未知' }}</span>
        </span>
      </div>
      <div class="kv-row">
        <span class="k">任务状态</span>
        <span class="v">{{ connected ? (robot.missionStatus ?? '未知') : '未知' }}</span>
      </div>
      <div class="kv-row">
        <span class="k">链路</span>
        <span class="v">
          <span class="tag-pill" :class="linkTone">{{ connected ? (robot.linkStatus ?? '未知') : '未知' }}</span>
          <span v-if="connected && robot.latencyMs !== null" class="muted mono" style="margin-left: 6px">
            {{ robot.latencyMs }}ms
          </span>
        </span>
      </div>
      <div class="kv-row">
        <span class="k">报警</span>
        <span class="v">
          <span v-if="!system.backendConnected" class="muted">未知</span>
          <span v-else-if="robot.alarm" class="tag-pill warn">{{ robot.alarm }}</span>
          <span v-else class="muted">无</span>
        </span>
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Aim } from '@element-plus/icons-vue'
import StatusDot from '@/components/common/StatusDot.vue'
import type { Robot } from '@/types'
import { connectionMethodText, connectionStateText, connectionTone, isRobotConnected } from '@/utils/connection'
import { useSystemStore } from '@/stores/system'

interface Props {
  robot: Robot
  isSelected: boolean
}
const props = defineProps<Props>()
const emit = defineEmits<{ (e: 'select', id: string): void }>()
const system = useSystemStore()
const connected = computed(() => system.backendConnected && isRobotConnected(props.robot))
const stateText = computed(() => system.backendConnected ? connectionStateText(props.robot.connection.state) : '状态未知')
const stateTone = computed(() => system.backendConnected ? connectionTone(props.robot.connection.state) : 'offline')
const methodText = computed(() => connected.value ? connectionMethodText(props.robot) : '未知')

const modeTone = computed(() => {
  if (!connected.value) return 'offline'
  switch (props.robot.mode) {
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

const typeLabel = computed(() => {
  switch (props.robot.robotType) {
    case 'uav': return '无人机'
    case 'usv': return '无人船'
    case 'dock': return '坞站'
    default: return '设备'
  }
})

const typeTone = computed(() => {
  switch (props.robot.robotType) {
    case 'uav': return 'info'
    case 'usv': return 'online'
    case 'dock': return 'warn'
    default: return 'offline'
  }
})
const linkTone = computed(() => {
  if (!connected.value) return 'offline'
  switch (props.robot.linkStatus) {
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
const batteryClass = computed(() => {
  const v = props.robot.battery
  if (v == null) return ''
  if (v <= 20) return 'critical'
  if (v <= 40) return 'low'
  return 'ok'
})

function onClick() {
  emit('select', props.robot.id)
}
</script>

<style scoped>
.card {
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.05s ease;
  position: relative;
}
.card:hover {
  border-color: var(--border-strong);
  background: var(--bg-panel-2);
}
.card.selected {
  border-color: var(--color-accent);
  box-shadow: 0 0 0 1px var(--color-accent), 0 0 14px rgba(59, 130, 246, 0.2);
}
.card.offline {
  opacity: 0.85;
}
.card.alarming::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
  background: linear-gradient(90deg, var(--color-warn), transparent);
  border-radius: var(--radius-md) var(--radius-md) 0 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.id-line {
  display: flex;
  align-items: center;
  gap: 10px;
}
.id {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-1);
}

.battery-bar {
  display: inline-block;
  width: 60px;
  height: 6px;
  background: var(--bg-panel-2);
  border: 1px solid var(--border);
  border-radius: 3px;
  position: relative;
  margin-right: 6px;
  overflow: hidden;
  vertical-align: middle;
}
.bar-fill {
  display: block;
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease;
}
.bar-fill.ok {
  background: var(--color-online);
}
.bar-fill.low {
  background: var(--color-warn);
}
.bar-fill.critical {
  background: var(--color-danger);
}

.select-flag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(59, 130, 246, 0.12);
  color: var(--color-accent);
  border: 1px solid rgba(59, 130, 246, 0.4);
  font-size: 10.5px;
  padding: 1px 6px;
  border-radius: 999px;
}
</style>
