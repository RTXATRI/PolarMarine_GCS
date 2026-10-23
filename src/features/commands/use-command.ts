import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { Command, CommandRequest, CommandStatus, CommandType } from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import { api, ApiError } from '@/shared/api/client'

const statusLabels: Record<CommandStatus, string> = {
  queued: '排队中',
  dispatched: '已发送',
  accepted: '设备已接受',
  in_progress: '执行中',
  completed: '已完成',
  rejected: '已拒绝',
  timed_out: 'ACK 超时',
  cancelled: '已取消',
  state_unconfirmed: '状态未确认'
}

export function useCommand() {
  const submitting = ref(false)
  const lastCommandId = ref<string | null>(null)
  const fleet = useFleetStore()
  const lastCommand = computed(() =>
    lastCommandId.value ? (fleet.commandsById[lastCommandId.value] ?? null) : null
  )

  async function submit(
    deviceId: string,
    commandType: CommandType,
    payload: Record<string, unknown>
  ): Promise<Command | null> {
    if (submitting.value) return null
    submitting.value = true
    try {
      const body: CommandRequest = { commandType, payload }
      const command = await api.submitCommand(deviceId, body)
      fleet.upsertCommand(command)
      lastCommandId.value = command.id
      if (command.status === 'rejected') {
        ElMessage.error(command.reasonMessage ?? '设备未接受命令')
      }
      return command
    } catch (error) {
      ElMessage.error(error instanceof ApiError ? error.message : '命令提交失败')
      return null
    } finally {
      submitting.value = false
    }
  }

  return { submitting, lastCommand, submit }
}

export function commandStatusLabel(status: CommandStatus): string {
  return statusLabels[status]
}

export function commandStatusClass(status: CommandStatus): string {
  if (status === 'completed') return 'success'
  if (status === 'rejected' || status === 'timed_out' || status === 'state_unconfirmed')
    return 'danger'
  if (status === 'accepted' || status === 'in_progress') return 'active'
  return 'pending'
}
