<template>
  <div class="manual-page">
    <section class="info-row panel">
      <div class="info-cell">
        <span>当前设备</span><b class="mono large">{{ fleet.selectedDevice?.id ?? '--' }}</b>
      </div>
      <div class="info-cell">
        <span>在线状态</span>
        <StatusDot
          v-if="fleet.selectedDevice"
          :tone="operationTone(fleet.selectedOperationalState?.status)"
          :label="operationText(fleet.selectedOperationalState?.status)"
        />
        <b v-else>--</b>
      </div>
      <div class="info-cell">
        <span>控制模式</span><b class="tag-pill" :class="modeTone">{{ modeText }}</b>
      </div>
      <div class="info-cell">
        <span>解锁状态</span>
        <b class="tag-pill" :class="armed === true ? 'online' : 'offline'">
          {{ armed == null ? '未知' : armed ? '已解锁' : '已锁定' }}
        </b>
      </div>
      <div class="info-cell">
        <span>当前速度</span><b class="mono">{{ valueText(telemetry, 'speed') }}</b>
      </div>
      <div class="info-cell">
        <span>航向</span><b class="mono">{{ valueText(telemetry, 'heading') }}</b>
      </div>
      <div class="info-cell">
        <span>链路延迟</span><b class="mono">{{ latencyText }}</b>
      </div>
      <button class="info-cell ack-cell" type="button" @click="commandDrawerVisible = true">
        <span>ACK</span>
        <b class="tag-pill" :class="latestCommandTone">{{ latestCommandText }}</b>
      </button>
    </section>

    <div class="control-layout">
      <section class="direction-panel panel">
        <h2 class="section-title">方向控制</h2>
        <DirectionalPad :disabled="!canManual" @command="sendManual" />
        <div v-if="!canManual" class="warning-tip">
          <el-icon><Warning /></el-icon><span>{{ manualDisabledReason }}</span>
        </div>
      </section>

      <section class="settings-panel panel">
        <h2 class="section-title">参数与模式</h2>
        <div class="form">
          <div class="form-row">
            <span class="label">速度档位</span>
            <el-radio-group v-model="speedGear" :disabled="!canManual">
              <el-radio-button value="low">低速 · 0.3</el-radio-button>
              <el-radio-button value="mid">中速 · 0.6</el-radio-button>
              <el-radio-button value="high">高速 · 1.0</el-radio-button>
            </el-radio-group>
            <span class="unit">m/s</span>
          </div>
          <div class="form-row">
            <span class="label">控制模式</span>
            <el-segmented
              :model-value="modeSelection"
              :options="modeOptions"
              :disabled="!canMode"
              @change="sendMode"
            />
            <span class="hint">切换结果以设备遥测为准</span>
          </div>
          <div class="form-row">
            <span class="label">解锁/锁定</span>
            <el-button
              :type="armed ? 'warning' : 'primary'"
              :disabled="!canArm"
              :loading="command.submitting.value"
              @click="toggleArmed"
            >
              <el-icon><Lock v-if="armed" /><Unlock v-else /></el-icon>
              {{ armed ? '请求锁定设备' : '请求解锁设备' }}
            </el-button>
            <span class="hint">设备端可因任务冲突或安全条件拒绝</span>
          </div>
        </div>

        <div class="emergency-row">
          <EmergencyButton />
          <div>
            <b>全链路急停</b>
            <span>逐链路 ACK 与最终状态确认可在命令详情中查看。</span>
          </div>
        </div>
      </section>
    </div>

    <el-drawer v-model="commandDrawerVisible" title="命令与逐链路 ACK" size="620px">
      <div v-if="deviceCommands.length" class="command-list">
        <article v-for="entry in deviceCommands" :key="entry.id">
          <header>
            <div>
              <b>{{ commandTypeLabel(entry.commandType) }}</b>
              <span class="mono">{{ entry.id }}</span>
            </div>
            <span class="command-status" :class="commandStatusClass(entry.status)">
              {{ commandStatusLabel(entry.status) }}
            </span>
          </header>
          <div class="command-meta">
            <span>提交 {{ formatTime(entry.createdAt) }}</span>
            <span v-if="entry.progress != null">进度 {{ Math.round(entry.progress * 100) }}%</span>
          </div>
          <div class="ack-list">
            <div v-for="linkId in entry.routedLinkIds" :key="linkId">
              <span>{{ fleet.linksById[linkId]?.displayName ?? linkId }}</span>
              <b class="mono">{{ entry.linkAcknowledgements[linkId] ?? 'pending' }}</b>
            </div>
            <span v-if="!entry.routedLinkIds.length" class="muted">尚未选择路由</span>
          </div>
          <p v-if="entry.reasonMessage" class="reason">
            {{ entry.reasonCode }} · {{ entry.reasonMessage }}
          </p>
        </article>
      </div>
      <div v-else class="drawer-empty">当前设备尚无命令记录</div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Lock, Unlock, Warning } from '@element-plus/icons-vue'
import type { CommandType } from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import DirectionalPad from '@/features/commands/DirectionalPad.vue'
import EmergencyButton from '@/features/commands/EmergencyButton.vue'
import { commandStatusClass, commandStatusLabel, useCommand } from '@/features/commands/use-command'
import {
  hasCapability,
  operationText,
  operationTone,
  validTelemetryValue,
  valueText
} from '@/shared/lib/device-view'
import { formatTime } from '@/shared/lib/presentation'
import StatusDot from '@/shared/ui/StatusDot.vue'

const fleet = useFleetStore()
const command = useCommand()
const speedGear = ref<'low' | 'mid' | 'high'>('low')
const commandDrawerVisible = ref(false)
const gearSpeed = { low: 0.3, mid: 0.6, high: 1.0 } as const
const modeOptions = [
  { label: '手动', value: 'manual' },
  { label: '自动', value: 'auto' }
]
const telemetry = computed(() => fleet.selectedTelemetry)
const activeSession = computed(() => {
  const linkId = fleet.selectedOperationalState?.activeLinkId
  return linkId ? fleet.sessionsByLinkId[linkId] : undefined
})
const deviceCommands = computed(() =>
  fleet.commands.filter((item) => item.deviceId === fleet.selectedDeviceId).slice(0, 30)
)
const latestCommand = computed(() => deviceCommands.value[0])
const modeText = computed(() => valueText(telemetry.value, 'control.mode', '未知'))
const modeSelection = computed(() => {
  const normalized = modeText.value.toLocaleLowerCase()
  return normalized.includes('auto') || normalized.includes('自动') ? 'auto' : 'manual'
})
const modeTone = computed(() => {
  const normalized = modeText.value.toLocaleLowerCase()
  if (normalized.includes('emergency') || normalized.includes('急停')) return 'danger'
  if (normalized.includes('auto') || normalized.includes('自动')) return 'online'
  if (normalized.includes('manual') || normalized.includes('手动')) return 'info'
  return 'offline'
})
const armed = computed<boolean | null>(() => {
  const field = validTelemetryValue(telemetry.value, 'control.armed')
  return typeof field?.value === 'boolean' ? field.value : null
})
const latencyText = computed(() =>
  activeSession.value?.latencyMs == null ? '--' : `${activeSession.value.latencyMs.toFixed(0)} ms`
)
const canManual = computed(
  () =>
    fleet.selectedOnline &&
    hasCapability(fleet.selectedTemplate, 'command.manual_control') &&
    !command.submitting.value
)
const canMode = computed(
  () => fleet.selectedOnline && hasCapability(fleet.selectedTemplate, 'command.mode_control')
)
const canArm = computed(
  () => fleet.selectedOnline && hasCapability(fleet.selectedTemplate, 'command.arm')
)
const manualDisabledReason = computed(() => {
  if (!fleet.selectedDevice) return '请先选择设备'
  if (!fleet.backendConnected) return '核心服务已断开'
  if (!fleet.selectedOnline) return '设备没有健康控制链路'
  if (!hasCapability(fleet.selectedTemplate, 'command.manual_control'))
    return '当前模板未声明手动控制能力'
  return '上一条命令正在提交'
})
const latestCommandText = computed(() =>
  latestCommand.value ? commandStatusLabel(latestCommand.value.status) : 'N/A'
)
const latestCommandTone = computed(() => {
  const status = latestCommand.value?.status
  if (status === 'completed') return 'online'
  if (status === 'accepted' || status === 'in_progress') return 'info'
  if (status === 'rejected' || status === 'timed_out' || status === 'state_unconfirmed')
    return 'danger'
  return 'offline'
})

async function sendManual(
  direction: 'forward' | 'backward' | 'left' | 'right' | 'stop'
): Promise<void> {
  if (!canManual.value) return
  await command.submit(fleet.selectedDeviceId, 'manual_control', {
    direction,
    speed: direction === 'stop' ? 0 : gearSpeed[speedGear.value],
    speedGear: speedGear.value
  })
}

async function sendMode(value: string | number | boolean): Promise<void> {
  if (!canMode.value || typeof value !== 'string') return
  await command.submit(fleet.selectedDeviceId, 'set_mode', { mode: value })
}

async function toggleArmed(): Promise<void> {
  if (!canArm.value) return
  await command.submit(fleet.selectedDeviceId, 'set_armed', { armed: armed.value !== true })
}

function commandTypeLabel(type: CommandType): string {
  const labels: Record<CommandType, string> = {
    manual_control: '手动控制',
    set_mode: '模式切换',
    set_armed: '解锁/锁定',
    emergency_stop: '紧急停止',
    return_home: '返航',
    start_mission: '启动任务',
    pause_mission: '暂停任务',
    resume_mission: '恢复任务',
    cancel_mission: '取消任务',
    read_parameters: '读取参数',
    write_parameters: '写入参数',
    custom_action: '自定义动作'
  }
  return labels[type]
}
</script>

<style scoped>
.manual-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.info-row {
  display: grid;
  grid-template-columns: repeat(8, minmax(0, 1fr));
  gap: 12px;
  flex: 0 0 auto;
  padding: 10px 14px;
}

.info-cell {
  display: flex;
  min-width: 0;
  flex-direction: column;
  align-items: flex-start;
  gap: 3px;
  padding: 0;
  color: var(--text-1);
  text-align: left;
  border: 0;
  background: transparent;
  font-family: inherit;
}

.info-cell > span:first-child {
  color: var(--text-3);
  font-size: 11px;
  letter-spacing: 0.04em;
}

.info-cell b {
  max-width: 100%;
  overflow: hidden;
  color: var(--text-1);
  font-size: 13px;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.info-cell b.large {
  font-size: 15px;
  font-weight: 700;
}

.ack-cell {
  cursor: pointer;
}

.ack-cell:hover b {
  filter: brightness(1.15);
}

.control-layout {
  display: grid;
  grid-template-columns: minmax(320px, auto) minmax(420px, 1fr);
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.control-layout > .panel {
  padding: 14px 16px;
}

.direction-panel {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 16px;
}

.warning-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  color: var(--color-warn);
  border: 1px solid rgb(245 158 11 / 40%);
  border-radius: 4px;
  background: rgb(245 158 11 / 10%);
  font-size: 12px;
}

.settings-panel {
  display: flex;
  flex-direction: column;
}

.form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 14px;
  min-height: 34px;
}

.label {
  flex: 0 0 82px;
  color: var(--text-3);
}

.hint,
.unit {
  color: var(--text-3);
  font-size: 11px;
}

.emergency-row {
  display: flex;
  align-items: center;
  gap: 14px;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
}

.emergency-row div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.emergency-row span {
  color: var(--text-3);
  font-size: 11.5px;
}

.command-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.command-list article {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel-2);
}

.command-list header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.command-list header div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.command-list header span {
  overflow: hidden;
  color: var(--text-3);
  font-size: 9px;
  text-overflow: ellipsis;
}

.command-status {
  padding: 2px 7px;
  color: var(--text-2);
  border-radius: 4px;
  background: rgb(148 163 184 / 10%);
  font-size: 10px;
  white-space: nowrap;
}

.command-status.success {
  color: var(--color-online);
}

.command-status.danger {
  color: var(--color-danger);
}

.command-status.active {
  color: var(--color-accent);
}

.command-meta {
  display: flex;
  gap: 12px;
  margin: 8px 0;
  color: var(--text-3);
  font-size: 10px;
}

.ack-list {
  display: grid;
  gap: 5px;
}

.ack-list div {
  display: flex;
  justify-content: space-between;
  padding: 5px 7px;
  border-radius: 3px;
  background: rgb(0 0 0 / 12%);
  font-size: 10.5px;
}

.reason {
  margin: 8px 0 0;
  color: var(--color-danger);
  font-size: 10.5px;
}

.drawer-empty {
  color: var(--text-3);
  text-align: center;
}

@media (width <= 1450px) {
  .info-row {
    gap: 8px;
  }

  .info-cell > span:first-child {
    font-size: 10px;
  }
}
</style>
