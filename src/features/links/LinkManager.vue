<template>
  <section class="link-manager">
    <header>
      <div>
        <span class="eyebrow">多链路路由</span>
        <h2>{{ fleet.selectedDevice?.displayName ?? '未选择设备' }}</h2>
      </div>
      <el-button :disabled="!fleet.selectedDevice" type="primary" size="small" @click="openCreate"
        >新增链路</el-button
      >
    </header>

    <div v-if="fleet.selectedLinks.length" class="links">
      <article
        v-for="link in fleet.selectedLinks"
        :key="link.id"
        class="link"
        :class="{ active: operation?.activeLinkId === link.id }"
      >
        <div class="link-head">
          <div>
            <b>{{ link.displayName }}</b>
            <small
              >{{ driverLabel(link.driver) }} ·
              {{ link.role === 'primary' ? '主链路' : '辅助链路' }} · P{{ link.priority }}</small
            >
          </div>
          <StatusBadge
            :label="sessionLabel(session(link.id)?.state ?? 'stopped')"
            :tone="sessionTone(session(link.id)?.state ?? 'stopped')"
          />
        </div>
        <div class="endpoint mono">{{ endpoint(link) }}</div>
        <div class="health">
          <span>延迟 {{ session(link.id)?.latencyMs ?? '--' }} ms</span>
          <span>丢包 {{ session(link.id)?.packetLossPercent ?? '--' }} %</span>
          <span v-if="operation?.activeLinkId === link.id" class="route">当前命令路由</span>
        </div>
        <p v-if="session(link.id)?.errorMessage" class="error">
          {{ session(link.id)?.errorCode }} · {{ session(link.id)?.errorMessage }}
        </p>
        <div class="actions">
          <el-button
            v-if="!isRunning(link.id)"
            :loading="busyLinkId === link.id"
            size="small"
            :disabled="!fleet.backendConnected"
            @click="connect(link.id)"
            >连接</el-button
          >
          <el-button
            v-else
            :loading="busyLinkId === link.id"
            size="small"
            @click="disconnect(link.id)"
            >断开</el-button
          >
          <el-button :disabled="isRunning(link.id)" size="small" @click="openEdit(link)"
            >编辑</el-button
          >
          <el-button
            :disabled="isRunning(link.id)"
            size="small"
            type="danger"
            plain
            @click="remove(link.id)"
            >删除</el-button
          >
        </div>
      </article>
    </div>
    <div v-else class="empty">尚未保存链路。添加 ROS1、ROS2、串口 JSON 或显式仿真链路。</div>

    <section v-if="routeChanges.length" class="route-history" aria-label="故障切换时间线">
      <div class="route-history-title"><b>故障切换时间线</b><small>来自后端持久化事件</small></div>
      <ol>
        <li v-for="change in routeChanges" :key="change.eventId">
          <time>{{ formatTime(change.occurredAt) }}</time>
          <span>{{ routeLinkName(change.payload.previousLinkId) }}</span>
          <span class="route-arrow">→</span>
          <b>{{ routeLinkName(change.payload.activeLinkId) }}</b>
        </li>
      </ol>
    </section>

    <el-dialog
      v-model="dialogVisible"
      :title="editingLinkId ? '编辑链路配置' : '新增链路配置'"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="显示名称"><el-input v-model="form.displayName" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="驱动协议">
            <el-select v-model="form.driver">
              <el-option label="ROS 1 / rosbridge" value="ros1" />
              <el-option label="ROS 2 / rosbridge" value="ros2" />
              <el-option label="串口 PolarMarine JSON" value="serial_json" />
              <el-option label="显式仿真（仅测试）" value="simulator" />
            </el-select>
          </el-form-item>
          <el-form-item label="角色"
            ><el-select v-model="form.role"
              ><el-option label="主链路" value="primary" /><el-option
                label="辅助链路"
                value="auxiliary" /></el-select
          ></el-form-item>
          <el-form-item label="优先级（越小越高）"
            ><el-input-number v-model="form.priority" :min="0" :max="10000"
          /></el-form-item>
        </div>
        <template v-if="form.driver === 'ros1' || form.driver === 'ros2'">
          <div class="discovery-row">
            <el-button :loading="discovering" size="small" @click="discoverNetwork"
              >mDNS 身份发现</el-button
            >
            <span>只列出广播 rosbridge 或 PolarMarine 身份的端点，不扫描网段。</span>
          </div>
          <el-select
            v-if="networkCandidates.length"
            class="candidate-select"
            placeholder="选择发现的端点"
            @change="selectCandidate"
          >
            <el-option
              v-for="candidate in networkCandidates"
              :key="candidate.host + ':' + candidate.port"
              :label="candidateLabel(candidate)"
              :value="candidate.host + ':' + candidate.port"
            />
          </el-select>
          <div class="form-grid two">
            <el-form-item label="设备 IP / 主机名"><el-input v-model="form.host" /></el-form-item
            ><el-form-item label="rosbridge 端口"
              ><el-input-number v-model="form.networkPort" :min="1" :max="65535"
            /></el-form-item>
          </div>
          <p class="hint">
            正式控制必须由设备端适配节点完成身份握手；普通 rosbridge 端点只能用于 ROS 调试。
          </p>
        </template>
        <template v-else-if="form.driver === 'serial_json'">
          <div class="discovery-row">
            <el-button :loading="enumeratingPorts" size="small" @click="enumerateSerialPorts"
              >刷新本机串口</el-button
            >
            <span>端口被占用、拔出或身份不匹配时，驱动会返回明确错误。</span>
          </div>
          <div class="form-grid two">
            <el-form-item label="串口"
              ><el-select v-model="form.serialPort" allow-create filterable placeholder="COM3"
                ><el-option
                  v-for="port in serialPorts"
                  :key="port.port"
                  :label="port.description ? port.port + ' · ' + port.description : port.port"
                  :value="port.port" /></el-select></el-form-item
            ><el-form-item label="波特率"
              ><el-select v-model="form.baudRate"
                ><el-option
                  v-for="rate in baudRates"
                  :key="rate"
                  :label="rate"
                  :value="rate" /></el-select
            ></el-form-item>
          </div>
        </template>
        <template v-else>
          <el-alert
            type="warning"
            :closable="false"
            title="该链路产生可复现的仿真数据，界面会永久标注“仿真数据”。"
          />
          <el-form-item label="随机种子"
            ><el-input-number v-model="form.seed" :min="0"
          /></el-form-item>
        </template>
      </el-form>
      <template #footer
        ><el-button @click="dialogVisible = false">取消</el-button
        ><el-button type="primary" :loading="saving" @click="save">保存配置</el-button></template
      >
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type {
  DriverKind,
  LinkProfile,
  LinkProfileWrite,
  LinkSessionState,
  NetworkDiscoveryCandidate
} from '@/entities/types'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import { api, ApiError } from '@/shared/api/client'
import { driverLabel, formatTime, sessionLabel } from '@/shared/lib/presentation'
import StatusBadge from '@/shared/ui/StatusBadge.vue'

const fleet = useFleetStore()
const events = useEventsStore()
const dialogVisible = ref(false)
const editingLinkId = ref<string | null>(null)
const saving = ref(false)
const busyLinkId = ref<string | null>(null)
const discovering = ref(false)
const enumeratingPorts = ref(false)
const networkCandidates = ref<NetworkDiscoveryCandidate[]>([])
const serialPorts = ref<Array<{ port: string; description?: string }>>([])
const baudRates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
const form = reactive({
  displayName: '主控制链路',
  driver: 'ros1' as DriverKind,
  role: 'primary' as LinkProfileWrite['role'],
  priority: 10,
  host: '127.0.0.1',
  networkPort: 9090,
  serialPort: '',
  baudRate: 115200,
  seed: 1
})
const operation = computed(() => fleet.selectedOperationalState)
const routeChanges = computed(() =>
  events.events
    .filter(
      (event) =>
        event.type === 'device.route_changed' && event.aggregateId === fleet.selectedDeviceId
    )
    .map((event) => ({
      ...event,
      payload: {
        previousLinkId: stringOrNull(event.payload.previousLinkId),
        activeLinkId: stringOrNull(event.payload.activeLinkId)
      }
    }))
    .slice(0, 5)
)
const session = (linkId: string) => fleet.sessionsByLinkId[linkId]
const isRunning = (linkId: string) =>
  !['stopped', 'failed'].includes(session(linkId)?.state ?? 'stopped')

async function save() {
  const deviceId = fleet.selectedDeviceId
  if (!deviceId || !form.displayName.trim()) return
  const config =
    form.driver === 'serial_json'
      ? { port: form.serialPort.trim(), baudRate: form.baudRate }
      : form.driver === 'simulator'
        ? { seed: form.seed }
        : { host: form.host.trim(), port: form.networkPort }
  const body: LinkProfileWrite = {
    displayName: form.displayName.trim(),
    driver: form.driver,
    role: form.role,
    priority: form.priority,
    config,
    enabled: true
  }
  saving.value = true
  try {
    const saved = editingLinkId.value
      ? await api.updateLink(deviceId, editingLinkId.value, body)
      : await api.createLink(deviceId, body)
    fleet.upsertLink(saved)
    dialogVisible.value = false
    ElMessage.success('链路配置已保存；当前仍未连接')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '保存链路失败')
  } finally {
    saving.value = false
  }
}

function openCreate() {
  editingLinkId.value = null
  Object.assign(form, {
    displayName: '主控制链路',
    driver: 'ros1',
    role: 'primary',
    priority: 10,
    host: '127.0.0.1',
    networkPort: 9090,
    serialPort: '',
    baudRate: 115200,
    seed: 1
  })
  networkCandidates.value = []
  dialogVisible.value = true
}

function openEdit(link: LinkProfile) {
  const config = link.config ?? {}
  editingLinkId.value = link.id
  Object.assign(form, {
    displayName: link.displayName,
    driver: link.driver,
    role: link.role,
    priority: link.priority,
    host: stringConfig(config, 'host', '127.0.0.1'),
    networkPort: numberConfig(config, 'port', 9090),
    serialPort: stringConfig(config, 'port', ''),
    baudRate: numberConfig(config, 'baudRate', 115200),
    seed: numberConfig(config, 'seed', 1)
  })
  networkCandidates.value = []
  dialogVisible.value = true
}

async function connect(linkId: string) {
  busyLinkId.value = linkId
  try {
    const receipt = await api.connectLink(fleet.selectedDeviceId, linkId)
    fleet.upsertSession(receipt.session)
    ElMessage.info('连接请求已提交，正在等待设备身份握手')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '连接失败')
  } finally {
    busyLinkId.value = null
  }
}

async function disconnect(linkId: string) {
  busyLinkId.value = linkId
  try {
    const receipt = await api.disconnectLink(fleet.selectedDeviceId, linkId)
    fleet.upsertSession(receipt.session)
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '断开失败')
  } finally {
    busyLinkId.value = null
  }
}

async function remove(linkId: string) {
  try {
    await ElMessageBox.confirm('删除这条已保存的链路配置？', '删除链路', { type: 'warning' })
    await api.deleteLink(fleet.selectedDeviceId, linkId)
    fleet.removeLink(linkId)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close')
      ElMessage.error(error instanceof ApiError ? error.message : '删除失败')
  }
}

async function discoverNetwork() {
  if (form.driver !== 'ros1' && form.driver !== 'ros2') return
  discovering.value = true
  try {
    const result = await api.discoverNetwork(form.driver)
    networkCandidates.value = result.candidates ?? []
    if (!networkCandidates.value.length) ElMessage.info('未发现广播端点，仍可手工填写地址')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '网络发现失败')
  } finally {
    discovering.value = false
  }
}

function selectCandidate(value: string) {
  const candidate = networkCandidates.value.find((item) => item.host + ':' + item.port === value)
  if (!candidate) return
  form.host = candidate.host
  form.networkPort = candidate.port
  if (candidate.deviceId && candidate.deviceId !== fleet.selectedDeviceId) {
    ElMessage.warning('该端点广播的设备身份与当前设备不一致，正式握手会拒绝连接')
  }
}

function candidateLabel(candidate: NetworkDiscoveryCandidate): string {
  const identity = candidate.deviceId ? ' · ' + candidate.deviceId : ' · 未声明身份'
  const verified = candidate.identityVerified ? ' · 已验证广播' : ' · 仅调试候选'
  return candidate.host + ':' + candidate.port + identity + verified
}

function stringConfig(config: Record<string, unknown>, key: string, fallback: string): string {
  return typeof config[key] === 'string' ? config[key] : fallback
}

function numberConfig(config: Record<string, unknown>, key: string, fallback: number): number {
  return typeof config[key] === 'number' ? config[key] : fallback
}

function stringOrNull(value: unknown): string | null {
  return typeof value === 'string' && value ? value : null
}

function routeLinkName(linkId: string | null): string {
  return linkId ? (fleet.linksById[linkId]?.displayName ?? linkId) : '无活动路由'
}

async function enumerateSerialPorts() {
  enumeratingPorts.value = true
  try {
    const result = await api.serialPorts()
    serialPorts.value = (result.ports ?? []).flatMap((item) =>
      typeof item.port === 'string'
        ? [
            {
              port: item.port,
              description: typeof item.description === 'string' ? item.description : undefined
            }
          ]
        : []
    )
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '串口枚举失败')
  } finally {
    enumeratingPorts.value = false
  }
}

function endpoint(link: LinkProfile): string {
  const config = link.config ?? {}
  if (link.driver === 'serial_json')
    return String(config.port ?? '--') + ' @ ' + String(config.baudRate ?? '--')
  if (link.driver === 'simulator') return 'seed=' + String(config.seed ?? 1) + ' · SIMULATED'
  return String(config.host ?? '--') + ':' + String(config.port ?? '--')
}

function sessionTone(state: LinkSessionState): 'neutral' | 'success' | 'warning' | 'danger' {
  if (state === 'healthy') return 'success'
  if (
    state === 'starting' ||
    state === 'handshaking' ||
    state === 'recovering' ||
    state === 'degraded'
  )
    return 'warning'
  if (state === 'failed') return 'danger'
  return 'neutral'
}
</script>

<style scoped>
.link-manager {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
}

.eyebrow {
  color: var(--text-3);
  font-size: 9px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

h2 {
  margin: 3px 0 0;
  font-size: 16px;
}

.links {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 10px;
  padding: 12px;
  overflow: auto;
}

.route-history {
  margin: 0 12px 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: rgb(0 0 0 / 12%);
}

.route-history-title {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
}

.route-history-title b {
  font-size: 11px;
}

.route-history-title small {
  color: var(--text-3);
  font-size: 9px;
}

.route-history ol {
  display: grid;
  gap: 5px;
  margin: 8px 0 0;
  padding: 0;
  list-style: none;
}

.route-history li {
  display: grid;
  grid-template-columns: 124px minmax(0, 1fr) 18px minmax(0, 1fr);
  align-items: center;
  color: var(--text-2);
  font-size: 10px;
}

.route-history time {
  color: var(--text-3);
  font-family: var(--font-mono);
}

.route-history li b,
.route-arrow {
  color: var(--color-accent);
}

.link {
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-app);
}

.link.active {
  border-color: var(--color-accent);
  box-shadow: inset 3px 0 var(--color-accent);
}

.link-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.link-head div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.link-head small,
.endpoint,
.health {
  color: var(--text-3);
  font-size: 10.5px;
}

.endpoint {
  margin-top: 10px;
  padding: 7px;
  border-radius: 4px;
  background: rgb(0 0 0 / 18%);
}

.health {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 9px;
}

.route {
  color: var(--color-accent);
}

.error {
  color: var(--color-danger);
  font-size: 10.5px;
}

.actions {
  display: flex;
  gap: 7px;
  margin-top: 11px;
}

.empty {
  margin: auto;
  padding: 28px;
  color: var(--text-3);
  text-align: center;
}

.form-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 12px;
}

.form-grid.two {
  grid-template-columns: 2fr 1fr;
}

.hint {
  margin-top: -4px;
  color: var(--text-3);
  font-size: 11px;
  line-height: 1.5;
}

.discovery-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  color: var(--text-3);
  font-size: 10.5px;
}

.candidate-select {
  width: 100%;
  margin-bottom: 12px;
}
</style>
