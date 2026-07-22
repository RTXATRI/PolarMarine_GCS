<template>
  <div class="device-area">
    <div v-if="!system.backendConnected" class="empty-state backend-down">
      <el-icon><WarningFilled /></el-icon>
      <strong>后端连接中断</strong>
      <span>设备状态暂不可确认，控制与摄像头已关闭，系统正在自动重连。</span>
      <el-button :loading="system.backendState === 'connecting'" @click="retryBackend">立即重试</el-button>
    </div>

    <div v-else-if="!robot" class="empty-state">请选择一个设备</div>

    <div v-else-if="robot.connection.state === 'connected'" class="connected-area">
      <div class="connection-summary">
        <div class="summary-main">
          <StatusDot tone="online" label="已连接" />
          <span class="method">{{ methodText }}</span>
          <span class="endpoint mono">{{ robot.connection.endpoint ?? '未知端点' }}</span>
          <span class="data-mode">{{ dataModeText }}</span>
        </div>
        <el-button type="danger" plain :loading="disconnecting" @click="disconnect">断开连接</el-button>
      </div>
      <div class="camera-wrap">
        <CameraGrid :robot-id="robot.id" />
      </div>
    </div>

    <div v-else-if="robot.connection.state === 'connecting'" class="empty-state connecting">
      <el-icon class="is-loading"><Loading /></el-icon>
      <strong>正在连接 {{ robot.id }}</strong>
      <span>{{ robot.connection.endpoint ?? '正在打开通信端点…' }}</span>
    </div>

    <ConnectionPanel v-else :robot="robot" />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Loading, WarningFilled } from '@element-plus/icons-vue'
import CameraGrid from '@/components/video/CameraGrid.vue'
import ConnectionPanel from '@/components/connection/ConnectionPanel.vue'
import StatusDot from '@/components/common/StatusDot.vue'
import { disconnectRobot } from '@/services/backend-api'
import { startBackendDataSource } from '@/services/data-source'
import { useRobotsStore } from '@/stores/robots'
import { useSystemStore } from '@/stores/system'
import type { Robot } from '@/types'

const props = defineProps<{ robot: Robot | null }>()
const robots = useRobotsStore()
const system = useSystemStore()
const disconnecting = ref(false)

const methodText = computed(() => {
  if (props.robot?.connection.activeMethod === 'serial') return '串口'
  if (props.robot?.connection.activeMethod === 'network') return '网络'
  return '未知'
})
const dataModeText = computed(() => {
  const connection = props.robot?.connection
  if (connection?.dataMode === 'virtual' || connection?.dataMode === 'live') return '数据已就绪'
  return '等待数据'
})

async function disconnect() {
  if (!props.robot || disconnecting.value) return
  const robotId = props.robot.id
  disconnecting.value = true
  try {
    const updated = await disconnectRobot(robotId)
    robots.applyRobot(updated)
    ElMessage.success(`${robotId} 已断开`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '断开设备失败')
  } finally {
    disconnecting.value = false
  }
}

function retryBackend() {
  void startBackendDataSource()
}
</script>

<style scoped>
.device-area { width: 100%; height: 100%; min-height: 0; }
.connected-area { height: 100%; display: grid; grid-template-rows: auto 1fr; min-height: 0; }
.connection-summary { min-height: 44px; padding: 7px 10px; display: flex; align-items: center; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--border); background: var(--bg-panel-2); }
.summary-main { display: flex; align-items: center; gap: 10px; min-width: 0; font-size: 12px; }
.method, .data-mode { padding: 2px 7px; border-radius: 999px; background: rgba(59, 130, 246, 0.1); color: var(--color-accent); }
.endpoint { color: var(--text-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.data-mode { color: var(--text-3); background: var(--bg-panel); }
.camera-wrap { min-height: 0; }
.empty-state { height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 28px; color: var(--text-3); text-align: center; background: var(--bg-panel); }
.empty-state .el-icon { font-size: 32px; }
.empty-state strong { color: var(--text-1); font-size: 15px; }
.backend-down .el-icon { color: var(--color-warn); }
.connecting .el-icon { color: var(--color-accent); }
</style>
