<template>
  <div class="connection-panel">
    <div class="panel-heading">
      <div>
        <div class="title">连接 {{ robot.id }}</div>
        <div class="subtitle">选择通信方式并打开设备连接</div>
      </div>
      <span class="state-tag" :class="robot.connection.state">{{ stateText }}</span>
    </div>

    <el-alert
      v-if="errorMessage"
      :title="errorMessage"
      type="error"
      :closable="false"
      show-icon
      class="connection-alert"
    />

    <div class="connection-form">
      <div class="form-row">
        <span class="label">连接方式</span>
        <el-radio-group v-model="method" :disabled="busy">
          <el-radio-button value="serial">串口</el-radio-button>
          <el-radio-button value="network">网络</el-radio-button>
        </el-radio-group>
      </div>

      <template v-if="method === 'serial'">
        <div class="form-row">
          <span class="label">串口设备</span>
          <el-select
            v-model="serialPort"
            filterable
            placeholder="选择已发现的串口"
            :loading="serialSearching"
            :disabled="busy"
            class="field"
          >
            <el-option
              v-for="item in serialOptions"
              :key="item.port"
              :label="serialLabel(item)"
              :value="item.port"
            />
          </el-select>
          <el-button :icon="Refresh" :loading="serialSearching" :disabled="busy" @click="searchSerialPorts">
            搜索硬件
          </el-button>
        </div>
        <div class="form-row">
          <span class="label">波特率</span>
          <el-select v-model="baudRate" :disabled="busy" class="field">
            <el-option v-for="rate in baudRates" :key="rate" :label="String(rate)" :value="rate" />
          </el-select>
        </div>
        <div v-if="serialSearched && serialOptions.length === 0" class="search-hint">
          未发现可用串口。请连接硬件后刷新；被系统隐藏或占用的端口可能不会出现在列表中。
        </div>
      </template>

      <template v-else>
        <div class="form-row">
          <span class="label">IP 地址</span>
          <el-select
            v-model="networkHost"
            filterable
            allow-create
            default-first-option
            placeholder="选择候选设备或手工输入 IPv4"
            :loading="networkSearching"
            :disabled="busy"
            class="field"
          >
            <el-option
              v-for="item in networkCandidates"
              :key="`${item.host}:${item.port}`"
              :label="networkLabel(item)"
              :value="item.host"
            />
          </el-select>
          <el-button :icon="Search" :loading="networkSearching" :disabled="busy" @click="searchNetwork">
            搜索局域网
          </el-button>
        </div>
        <div class="form-row">
          <span class="label">端口</span>
          <el-input-number v-model="networkPort" :min="1" :max="65535" :controls="false" :disabled="busy" class="field" />
        </div>
        <div class="search-hint">
          <template v-if="robot.robotType === 'dock'">
            搜索只提供当前局域网候选；也可以手工输入未被发现的 IPv4 地址。
          </template>
          <template v-else>
            请输入机载电脑 ROSBridge 地址；连接会在收到 /gcs/robot_state 首帧后完成。
          </template>
        </div>
      </template>

      <div class="actions">
        <el-button
          type="primary"
          :icon="Connection"
          :loading="busy"
          :disabled="!canSubmit"
          @click="submit"
        >
          {{ robot.connection.state === 'error' ? '重新连接' : '连接设备' }}
        </el-button>
        <span v-if="!system.backendConnected" class="backend-warning">后端未连接，暂时不能操作设备</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Connection, Refresh, Search } from '@element-plus/icons-vue'
import { connectRobot, fetchNetworkCandidates, fetchSerialPorts } from '@/services/backend-api'
import { ApiError } from '@/services/http'
import { useRobotsStore } from '@/stores/robots'
import { useSystemStore } from '@/stores/system'
import type { ConnectionMethod, ConnectionProfile, NetworkCandidate, Robot, SerialPortInfo } from '@/types'

const props = defineProps<{ robot: Robot }>()

const robots = useRobotsStore()
const system = useSystemStore()
const method = ref<ConnectionMethod>('serial')
const serialPort = ref('')
const baudRate = ref(115200)
const networkHost = ref('')
const networkPort = ref(9090)
const serialPorts = ref<SerialPortInfo[]>([])
const networkCandidates = ref<NetworkCandidate[]>([])
const serialSearching = ref(false)
const networkSearching = ref(false)
const serialSearched = ref(false)
const submitting = ref(false)
const localError = ref<string | null>(null)
const baudRates = [9600, 19200, 38400, 57600, 115200]

const busy = computed(() => submitting.value || props.robot.connection.state === 'connecting')
const errorMessage = computed(() => localError.value ?? props.robot.connection.error?.message ?? null)
const stateText = computed(() => {
  if (props.robot.connection.state === 'error') return '连接失败'
  if (props.robot.connection.state === 'connecting') return '连接中'
  return '未连接'
})
const serialOptions = computed(() => {
  if (!serialPort.value || serialPorts.value.some(item => item.port === serialPort.value)) return serialPorts.value
  return [{ port: serialPort.value, description: '上次保存的串口' }, ...serialPorts.value]
})
const canSubmit = computed(() => {
  if (!system.backendConnected || busy.value) return false
  if (method.value === 'serial') return !!serialPort.value && baudRate.value > 0
  return isIPv4(networkHost.value) && networkPort.value >= 1 && networkPort.value <= 65535
})

function hydrateProfile() {
  const profile = props.robot.connectionProfile
  localError.value = null
  method.value = 'serial'
  serialPort.value = ''
  baudRate.value = 115200
  networkHost.value = ''
  networkPort.value = 9090
  if (!profile) return
  method.value = profile.method
  if (profile.method === 'serial') {
    serialPort.value = profile.port
    baudRate.value = profile.baudRate
  } else {
    networkHost.value = profile.host
    networkPort.value = profile.port
  }
}

function isIPv4(value: string): boolean {
  const parts = value.trim().split('.')
  return parts.length === 4 && parts.every(part => /^\d{1,3}$/.test(part) && Number(part) <= 255)
}

function serialLabel(item: SerialPortInfo): string {
  const detail = item.description && item.description !== item.port ? ` · ${item.description}` : ''
  return `${item.port}${detail}`
}

function networkLabel(item: NetworkCandidate): string {
  const name = item.hostname ? ` · ${item.hostname}` : ''
  const latency = item.latencyMs == null ? '' : ` · ${item.latencyMs}ms`
  return `${item.host}${name}${latency}`
}

function describeError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : fallback
}

async function searchSerialPorts() {
  serialSearching.value = true
  localError.value = null
  try {
    serialPorts.value = await fetchSerialPorts()
    serialSearched.value = true
  } catch (error) {
    serialSearched.value = true
    localError.value = describeError(error, '串口搜索失败')
  } finally {
    serialSearching.value = false
  }
}

async function searchNetwork() {
  networkSearching.value = true
  localError.value = null
  try {
    networkCandidates.value = await fetchNetworkCandidates(networkPort.value)
    if (networkCandidates.value.length === 0) ElMessage.info('未发现候选设备，仍可手工输入 IP 地址')
  } catch (error) {
    localError.value = describeError(error, '局域网搜索失败')
  } finally {
    networkSearching.value = false
  }
}

async function submit() {
  if (!canSubmit.value) return
  const robotId = props.robot.id
  const profile: ConnectionProfile = method.value === 'serial'
    ? { method: 'serial', port: serialPort.value, baudRate: baudRate.value }
    : { method: 'network', host: networkHost.value.trim(), port: networkPort.value }

  submitting.value = true
  localError.value = null
  try {
    const updated = await connectRobot(robotId, profile)
    robots.applyRobot(updated)
    ElMessage.success(`${robotId} 已连接`)
  } catch (error) {
    if (error instanceof ApiError && typeof error.detail === 'object' && error.detail?.robot) {
      robots.applyRobot(error.detail.robot as Robot)
    }
    if (props.robot.id === robotId) {
      localError.value = describeError(error, '设备连接失败')
    }
  } finally {
    submitting.value = false
  }
}

watch(() => props.robot.id, hydrateProfile, { immediate: true })
// Robot objects are replaced by every WebSocket snapshot. Do not watch the
// profile object here: an unchanged saved profile would otherwise overwrite
// the user's in-progress method/IP/port draft on every telemetry tick.
watch(method, next => {
  localError.value = null
  if (next === 'serial' && !serialSearched.value) void searchSerialPorts()
  if (next === 'network' && networkCandidates.value.length === 0) void searchNetwork()
})

onMounted(() => {
  if (method.value === 'serial') void searchSerialPorts()
  else void searchNetwork()
})
</script>

<style scoped>
.connection-panel {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
  background:
    radial-gradient(circle at 85% 8%, rgba(59, 130, 246, 0.12), transparent 34%),
    var(--bg-panel);
}
.panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.title { color: var(--text-1); font-size: 18px; font-weight: 700; }
.subtitle { margin-top: 5px; color: var(--text-3); font-size: 12px; }
.state-tag { padding: 4px 9px; border: 1px solid var(--border); border-radius: 999px; color: var(--text-3); font-size: 11px; }
.state-tag.error { color: var(--color-danger); border-color: rgba(239, 68, 68, 0.45); }
.state-tag.connecting { color: var(--color-accent); border-color: rgba(59, 130, 246, 0.45); }
.connection-alert { margin-top: 18px; }
.connection-form { width: min(680px, 100%); margin-top: 26px; display: flex; flex-direction: column; gap: 16px; }
.form-row { display: grid; grid-template-columns: 84px minmax(220px, 1fr) auto; align-items: center; gap: 10px; }
.label { color: var(--text-2); font-size: 12.5px; }
.field { width: 100%; }
.search-hint { margin-left: 94px; color: var(--text-3); font-size: 11.5px; line-height: 1.55; }
.actions { margin-left: 94px; display: flex; align-items: center; gap: 12px; padding-top: 8px; }
.backend-warning { color: var(--color-warn); font-size: 12px; }
@media (max-width: 900px) {
  .form-row { grid-template-columns: 80px minmax(160px, 1fr); }
  .form-row > :last-child:not(:nth-child(2)) { grid-column: 2; }
}
</style>
