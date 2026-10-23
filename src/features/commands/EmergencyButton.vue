<template>
  <el-tooltip :content="disabledReason || '向全部健康控制链路发送急停，并等待设备状态确认'">
    <span>
      <el-popconfirm
        width="330"
        title="确认向当前设备发送急停？请求会投递到全部健康控制链路。"
        confirm-button-text="确认急停"
        cancel-button-text="取消"
        :disabled="Boolean(disabledReason)"
        @confirm="sendEmergencyStop"
      >
        <template #reference>
          <el-button
            class="emergency-button"
            type="danger"
            :size="compact ? 'small' : 'large'"
            :disabled="Boolean(disabledReason)"
            :loading="submitting"
          >
            <el-icon><WarningFilled /></el-icon>
            {{ compact ? '急停' : '紧急停止' }}
          </el-button>
        </template>
      </el-popconfirm>
    </span>
  </el-tooltip>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { WarningFilled } from '@element-plus/icons-vue'
import { useFleetStore } from '@/entities/fleet/store'
import { useCommand } from '@/features/commands/use-command'
import { hasCapability } from '@/shared/lib/device-view'

withDefaults(defineProps<{ compact?: boolean }>(), { compact: false })

const fleet = useFleetStore()
const { submit, submitting } = useCommand()
const disabledReason = computed(() => {
  if (!fleet.backendConnected) return '核心服务已断开'
  if (!fleet.selectedDevice) return '请先选择设备'
  if (!hasCapability(fleet.selectedTemplate, 'command.emergency_stop'))
    return '当前模板未声明急停能力'
  if (!fleet.selectedOnline) return '设备没有健康控制链路'
  return ''
})

async function sendEmergencyStop(): Promise<void> {
  const deviceId = fleet.selectedDeviceId
  if (!deviceId || disabledReason.value) return
  const command = await submit(deviceId, 'emergency_stop', {})
  if (command && command.status !== 'rejected') {
    ElMessage.info('急停请求已提交，正在等待逐链路 ACK 与设备状态确认')
  }
}
</script>

<style scoped>
.emergency-button {
  min-width: 76px;
  border-color: rgb(239 68 68 / 72%);
  box-shadow: 0 0 12px rgb(239 68 68 / 16%);
  font-weight: 700;
}
</style>
