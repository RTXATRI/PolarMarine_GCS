<template>
  <section class="quick-connection">
    <div v-if="!fleet.backendConnected" class="empty-state backend-down">
      <el-icon><WarningFilled /></el-icon>
      <strong>核心服务连接中断</strong>
      <span>设备运行状态不可确认，控制和本机摄像头均已关闭。</span>
      <el-button :loading="retrying" @click="retry">立即重试</el-button>
    </div>

    <div v-else-if="!fleet.selectedDevice" class="empty-state">请选择一个设备</div>

    <template v-else-if="fleet.selectedOnline">
      <div class="connection-summary">
        <div class="summary-main">
          <StatusDot
            :tone="operation?.status === 'online' ? 'online' : 'warn'"
            :label="operation?.status === 'online' ? '已连接' : '降级运行'"
          />
          <span class="method">{{
            activeProfile ? driverLabel(activeProfile.driver) : '多链路'
          }}</span>
          <span class="endpoint mono">{{ activeProfile?.displayName ?? '路由更新中' }}</span>
          <span class="health">
            健康 {{ operation?.healthyLinkIds.length ?? 0 }} / {{ fleet.selectedLinks.length }}
          </span>
        </div>
        <div class="summary-actions">
          <el-button size="small" @click="openDeviceManagement">设备管理</el-button>
          <el-button
            v-if="activeProfile"
            type="danger"
            plain
            size="small"
            :loading="busyLinkId === activeProfile.id"
            @click="disconnect(activeProfile.id)"
          >
            断开活动链路
          </el-button>
        </div>
      </div>
      <div class="camera-wrap">
        <MediaGrid
          v-if="fleet.selectedTemplate"
          :key="fleet.selectedDevice.id"
          :device-id="fleet.selectedDevice.id"
          :channels="fleet.selectedTemplate.mediaChannels ?? []"
          :online="true"
        />
      </div>
    </template>

    <div v-else class="offline-area">
      <div class="offline-head">
        <div>
          <strong>{{ fleet.selectedDevice.displayName }}</strong>
          <span>设备离线 · 选择已保存链路快速连接</span>
        </div>
        <el-button size="small" @click="openDeviceManagement">编辑链路</el-button>
      </div>
      <div v-if="fleet.selectedLinks.length" class="saved-links">
        <article v-for="link in fleet.selectedLinks" :key="link.id">
          <div class="link-identity">
            <StatusDot
              :tone="linkStateTone(fleet.sessionsByLinkId[link.id]?.state)"
              :label="sessionLabel(fleet.sessionsByLinkId[link.id]?.state ?? 'stopped')"
            />
            <div>
              <b>{{ link.displayName }}</b>
              <span class="mono">{{ endpoint(link) }}</span>
            </div>
          </div>
          <div class="link-meta">
            <span class="tag-pill info">{{ driverLabel(link.driver) }}</span>
            <span
              >{{ link.role === 'primary' ? '主链路' : '辅助链路' }} · P{{ link.priority }}</span
            >
          </div>
          <el-button
            type="primary"
            size="small"
            :loading="busyLinkId === link.id"
            :disabled="isStarting(link.id)"
            @click="connect(link.id)"
          >
            {{ isStarting(link.id) ? '连接中' : '连接' }}
          </el-button>
        </article>
      </div>
      <div v-else class="no-links">
        <el-icon><Connection /></el-icon>
        <strong>尚未保存链路</strong>
        <span>请到设备管理添加 ROS、串口或显式仿真链路。</span>
        <el-button type="primary" @click="openDeviceManagement">配置链路</el-button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Connection, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { LinkProfile } from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import MediaGrid from '@/features/media/MediaGrid.vue'
import { api, ApiError } from '@/shared/api/client'
import { refreshServerState } from '@/shared/api/data-source'
import { linkStateTone } from '@/shared/lib/device-view'
import { driverLabel, sessionLabel } from '@/shared/lib/presentation'
import StatusDot from '@/shared/ui/StatusDot.vue'

const fleet = useFleetStore()
const router = useRouter()
const busyLinkId = ref<string | null>(null)
const retrying = ref(false)
const operation = computed(() => fleet.selectedOperationalState)
const activeProfile = computed(() => {
  const linkId = operation.value?.activeLinkId
  return linkId ? fleet.linksById[linkId] : undefined
})

async function retry(): Promise<void> {
  retrying.value = true
  try {
    await refreshServerState()
    ElMessage.success('核心服务已恢复连接')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '核心服务仍不可用')
  } finally {
    retrying.value = false
  }
}

async function connect(linkId: string): Promise<void> {
  busyLinkId.value = linkId
  try {
    const receipt = await api.connectLink(fleet.selectedDeviceId, linkId)
    fleet.upsertSession(receipt.session)
    ElMessage.info('连接请求已提交，正在等待设备身份握手')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '连接请求失败')
  } finally {
    busyLinkId.value = null
  }
}

async function disconnect(linkId: string): Promise<void> {
  busyLinkId.value = linkId
  try {
    const receipt = await api.disconnectLink(fleet.selectedDeviceId, linkId)
    fleet.upsertSession(receipt.session)
    ElMessage.info('断开请求已提交')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '断开请求失败')
  } finally {
    busyLinkId.value = null
  }
}

function isStarting(linkId: string): boolean {
  return ['starting', 'handshaking', 'recovering'].includes(
    fleet.sessionsByLinkId[linkId]?.state ?? 'stopped'
  )
}

function endpoint(link: LinkProfile): string {
  const config = link.config ?? {}
  if (link.driver === 'serial_json')
    return `${String(config.port ?? '--')} @ ${String(config.baudRate ?? '--')}`
  if (link.driver === 'simulator') return `seed=${String(config.seed ?? 1)} · SIMULATED`
  return `${String(config.host ?? '--')}:${String(config.port ?? '--')}`
}

function openDeviceManagement(): void {
  void router.push('/devices')
}
</script>

<style scoped>
.quick-connection {
  width: 100%;
  height: 100%;
  min-height: 0;
}

.quick-connection > template,
.camera-wrap {
  min-height: 0;
}

.connection-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 44px;
  padding: 7px 10px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-panel-2);
}

.summary-main,
.summary-actions {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.method,
.health {
  padding: 2px 7px;
  color: var(--color-accent);
  border-radius: 999px;
  background: rgb(59 130 246 / 10%);
  font-size: 11px;
  white-space: nowrap;
}

.health {
  color: var(--text-3);
  background: var(--bg-panel);
}

.endpoint {
  overflow: hidden;
  color: var(--text-2);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.camera-wrap {
  height: calc(100% - 44px);
}

.empty-state,
.no-links {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  padding: 28px;
  color: var(--text-3);
  text-align: center;
}

.empty-state .el-icon,
.no-links .el-icon {
  color: var(--color-accent);
  font-size: 32px;
}

.backend-down .el-icon {
  color: var(--color-warn);
}

.empty-state strong,
.no-links strong {
  color: var(--text-1);
  font-size: 15px;
}

.offline-area {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.offline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}

.offline-head div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.offline-head span {
  color: var(--text-3);
  font-size: 11px;
}

.saved-links {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 10px;
  padding: 12px;
  overflow: auto;
}

.saved-links article {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-app);
}

.link-identity {
  display: flex;
  grid-column: 1 / -1;
  align-items: flex-start;
  gap: 12px;
}

.link-identity div {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.link-identity span {
  overflow: hidden;
  color: var(--text-3);
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.link-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-3);
  font-size: 10px;
}
</style>
