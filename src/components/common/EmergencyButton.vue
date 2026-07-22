<template>
  <el-popconfirm
    :title="confirmTitle"
    :confirm-button-text="'确认急停'"
    :cancel-button-text="'取消'"
    confirm-button-type="danger"
    width="260"
    :icon-color="'#ef4444'"
    @confirm="onConfirm"
  >
    <template #reference>
      <button class="estop-btn" :class="{ compact, large }" type="button" :disabled="!canStop" :title="disabledReason">
        <span class="ring" />
        <span class="text">急停</span>
      </button>
    </template>
  </el-popconfirm>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useLogsStore } from '@/stores/logs'
import { useRobotsStore } from '@/stores/robots'
import { postEmergencyStop } from '@/services/backend-api'
import { useSystemStore } from '@/stores/system'
import { hasCommandChannel, isRobotConnected } from '@/utils/connection'

interface Props {
  /** 紧凑型(顶栏使用) */
  compact?: boolean
  /** 大号(手动控制页使用) */
  large?: boolean
}
withDefaults(defineProps<Props>(), { compact: false, large: false })

const robots = useRobotsStore()
const logs = useLogsStore()
const system = useSystemStore()
const canStop = computed(() => system.backendConnected && hasCommandChannel(robots.selected))
const disabledReason = computed(() => {
  if (!system.backendConnected) return '后端连接中断'
  if (!isRobotConnected(robots.selected)) return '设备未连接'
  if (!hasCommandChannel(robots.selected)) return '当前连接尚无可用操作通道'
  return ''
})

const confirmTitle = computed(() => {
  const id = robots.selectedId || '当前设备'
  return `确认对 ${id} 触发急停?`
})

async function onConfirm() {
  const r = robots.selected
  if (!r) return

  if (!canStop.value) return
  try {
    const updated = await postEmergencyStop(r.id)
    robots.applyRobot(updated)
    logs.append('操作', r.id, '急停指令已发送')
    ElMessage.success('急停指令发送成功')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '急停命令发送失败')
  }
}
</script>

<style scoped>
.estop-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #ff5e5e, #c92a2a);
  color: #fff;
  font-weight: 700;
  letter-spacing: 0.18em;
  border: 1px solid #7a1414;
  border-radius: 6px;
  cursor: pointer;
  user-select: none;
  padding: 6px 14px;
  font-size: 13px;
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.25),
    0 2px 6px rgba(239, 68, 68, 0.45);
  transition: transform 0.05s ease, box-shadow 0.15s ease;
}
.estop-btn.compact {
  padding: 4px 12px;
  font-size: 12.5px;
}
.estop-btn.large {
  padding: 14px 28px;
  font-size: 16px;
  border-radius: 999px;
}
.estop-btn:hover {
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.3),
    0 2px 12px rgba(239, 68, 68, 0.65);
}
.estop-btn:active {
  transform: translateY(1px);
}
.estop-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
  box-shadow: none;
}
.estop-btn:disabled .ring { animation: none; }
.ring {
  position: absolute;
  inset: -3px;
  border-radius: inherit;
  border: 1px solid rgba(239, 68, 68, 0.5);
  animation: pulse-ring 1.6s infinite;
  pointer-events: none;
}
.text {
  position: relative;
}

@keyframes pulse-ring {
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.55);
  }
  100% {
    box-shadow: 0 0 0 10px rgba(239, 68, 68, 0);
  }
}
</style>
