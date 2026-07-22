<template>
  <div class="manual">
    <div class="info-row panel">
      <div class="info-cell">
        <div class="k">当前设备</div>
        <div class="v mono big">{{ r?.id ?? '--' }}</div>
      </div>
      <div class="info-cell">
        <div class="k">在线状态</div>
        <div class="v">
          <StatusDot v-if="r" :tone="connectionToneValue" :label="connectionText" />
          <span v-else class="muted">--</span>
        </div>
      </div>
      <div class="info-cell">
        <div class="k">控制模式</div>
        <div class="v">
          <span v-if="r" class="tag-pill" :class="modeTone">{{ dataAvailable ? (r.mode ?? '未知') : '未知' }}</span>
          <span v-else class="muted">--</span>
        </div>
      </div>
      <div class="info-cell">
        <div class="k">解锁状态</div>
        <div class="v">
          <span class="tag-pill" :class="dataAvailable && r?.unlocked ? 'online' : 'offline'">
            {{ !dataAvailable || r?.unlocked == null ? '未知' : (r.unlocked ? '已解锁' : '已锁定') }}
          </span>
        </div>
      </div>
      <div class="info-cell">
        <div class="k">当前速度</div>
        <div class="v mono">{{ formatNum(dataAvailable ? (r?.speed ?? null) : null, 'm/s', 2) }}</div>
      </div>
      <div class="info-cell">
        <div class="k">航向</div>
        <div class="v mono">{{ formatNum(dataAvailable ? (r?.heading ?? null) : null, '°', 0) }}</div>
      </div>
      <div class="info-cell">
        <div class="k">链路延迟</div>
        <div class="v mono">{{ formatNum(dataAvailable ? (r?.latencyMs ?? null) : null, 'ms', 0) }}</div>
      </div>
      <div class="info-cell">
        <div class="k">ACK</div>
        <div class="v">
          <span class="tag-pill" :class="ackTone">{{ ackText }}</span>
        </div>
      </div>
    </div>

    <div class="layout">
      <div class="left panel">
        <div class="section-title">方向控制</div>
        <DPad :disabled="!canControl" @cmd="onDirCmd" />
        <div v-if="!canControl" class="warn-tip">
          <el-icon><Warning /></el-icon>
          <span>{{ disableReason }}</span>
        </div>
      </div>

      <div class="right panel">
        <div class="section-title">参数与模式</div>
        <div class="form">
          <div class="form-row">
            <span class="lbl">速度档位</span>
            <el-radio-group v-model="speedGear" :disabled="!canControl" @change="onSpeedGearChange">
              <el-radio-button value="low">低速</el-radio-button>
              <el-radio-button value="mid">中速</el-radio-button>
              <el-radio-button value="high">高速</el-radio-button>
            </el-radio-group>
          </div>
          <div class="form-row">
            <span class="lbl">控制模式</span>
            <el-segmented
              v-model="modeValue"
              :options="modeOptions"
              :disabled="!canUseChannel"
              @change="onModeSwitch"
            />
          </div>
          <div class="form-row">
            <span class="lbl">解锁/锁定</span>
            <el-button :type="r?.unlocked ? 'warning' : 'primary'" :disabled="!canControl" @click="toggleUnlock">
              <el-icon><Unlock v-if="!r?.unlocked" /><Lock v-else /></el-icon>
              <span>{{ r?.unlocked ? '锁定设备' : '解锁设备' }}</span>
            </el-button>
          </div>
        </div>

        <div class="estop-row">
          <EmergencyButton large />
          <div class="muted small">急停将立即停止当前选中设备并切换为急停模式</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Lock, Unlock, Warning } from '@element-plus/icons-vue'
import StatusDot from '@/components/common/StatusDot.vue'
import DPad from '@/components/manual/DPad.vue'
import EmergencyButton from '@/components/common/EmergencyButton.vue'
import { useRobotsStore } from '@/stores/robots'
import { useLogsStore } from '@/stores/logs'
import { postLockCommand, postManualCommand, postModeCommand } from '@/services/backend-api'
import type { ControlMode } from '@/types'
import { useSystemStore } from '@/stores/system'
import { connectionStateText, connectionTone, hasCommandChannel, hasUsableDataChannel, isRobotConnected } from '@/utils/connection'

const robots = useRobotsStore()
const logs = useLogsStore()
const system = useSystemStore()
const r = computed(() => robots.selected)
const connected = computed(() => system.backendConnected && isRobotConnected(r.value))
const dataAvailable = computed(() => system.backendConnected && hasUsableDataChannel(r.value))
const canUseChannel = computed(() => system.backendConnected && hasCommandChannel(r.value))
const canControl = canUseChannel
const connectionText = computed(() => {
  if (!system.backendConnected) return '状态未知'
  return r.value ? connectionStateText(r.value.connection.state) : '--'
})
const connectionToneValue = computed(() => {
  if (!system.backendConnected || !r.value) return 'offline' as const
  return connectionTone(r.value.connection.state)
})

const disableReason = computed(() => {
  if (!r.value) return '请先选择一个设备'
  if (!system.backendConnected) return '后端连接中断，无法控制'
  if (!connected.value) return '设备未连接，无法控制'
  if (!canUseChannel.value) return '连接已打开，但操作反馈通道尚不可用'
  return ''
})

const modeTone = computed(() => {
  if (!dataAvailable.value) return 'offline'
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

const speedGear = ref<'low' | 'mid' | 'high'>('low')
const gearSpeed: Record<'low' | 'mid' | 'high', number> = { low: 0.3, mid: 0.6, high: 1.0 }

const modeOptions = [
  { label: '手动', value: '手动' },
  { label: '自动', value: '自动' }
]
const modeValue = ref<string>(r.value?.mode === '自动' ? '自动' : '手动')

watch(
  () => r.value?.mode,
  m => {
    if (m === '手动' || m === '自动') modeValue.value = m
  }
)

const ackText = computed(() => {
  if (!dataAvailable.value || !r.value) return 'N/A'
  if (r.value.linkStatus === '断开') return '超时'
  if (r.value.linkStatus === '正常') return 'OK'
  return '抖动'
})
const ackTone = computed(() => {
  switch (ackText.value) {
    case 'OK':
      return 'online'
    case '抖动':
      return 'warn'
    case '超时':
      return 'danger'
    default:
      return 'offline'
  }
})

function ensureCanControl(): boolean {
  if (!canControl.value) {
    ElMessage.warning(disableReason.value || '设备离线,无法控制')
    return false
  }
  return true
}

async function onDirCmd(d: '前进' | '后退' | '左转' | '右转' | '停止') {
  if (!ensureCanControl()) return
  const robot = r.value!
  const sp = gearSpeed[speedGear.value]
  try {
    const updated = await postManualCommand(robot.id, d, d === '停止' ? 0 : sp, speedGear.value)
    robots.applyRobot(updated)
    logs.append('操作', robot.id, `手动指令:${d}(档位 ${speedGear.value})`)
    ElMessage.success('指令发送成功')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端手动指令发送失败')
  }
}

function onSpeedGearChange(val: string | number | boolean | undefined) {
  if (!r.value) return
  logs.append('操作', r.value.id, `切换速度档位为 ${val}`)
}

async function onModeSwitch(val: string | number | boolean | undefined) {
  if (!r.value) return
  const mode = val as ControlMode
  if (!canUseChannel.value) return
  try {
    const updated = await postModeCommand(r.value.id, mode as '手动' | '自动')
    robots.applyRobot(updated)
    logs.append('操作', r.value.id, `切换控制模式为 ${mode}`)
    ElMessage.success('模式切换指令发送成功')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端模式切换失败')
  }
}

async function toggleUnlock() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    const updated = await postLockCommand(robot.id, robot.unlocked !== true)
    robots.applyRobot(updated)
    const action = robot.unlocked === true ? '锁定' : '解锁'
    logs.append('操作', robot.id, `${action}设备指令已发送`)
    ElMessage.success(`${action}指令发送成功`)
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端解锁/锁定失败')
  }
}

function formatNum(v: number | null, unit: string, digits: number) {
  if (v == null) return '--'
  return `${v.toFixed(digits)} ${unit}`
}
</script>

<style scoped>
.manual {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.info-row {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 12px;
  padding: 10px 14px;
}
.info-cell .k {
  font-size: 11px;
  color: var(--text-3);
  letter-spacing: 0.04em;
}
.info-cell .v {
  font-size: 14px;
  color: var(--text-1);
  margin-top: 2px;
}
.info-cell .v.big {
  font-size: 16px;
  font-weight: 700;
}

.layout {
  display: grid;
  grid-template-columns: minmax(320px, auto) 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}
.layout > .panel {
  padding: 14px 16px;
}
.left {
  display: flex;
  flex-direction: column;
  gap: 16px;
  align-items: flex-start;
}
.warn-tip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.4);
  color: var(--color-warn);
  border-radius: 4px;
  font-size: 12.5px;
}
.right {
  display: flex;
  flex-direction: column;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-bottom: 24px;
}
.form-row {
  display: flex;
  align-items: center;
  gap: 14px;
}
.form-row .lbl {
  width: 80px;
  color: var(--text-3);
  font-size: 12.5px;
}
.estop-row {
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
  display: flex;
  align-items: center;
  gap: 14px;
}
.estop-row .small {
  font-size: 11.5px;
}
</style>
