import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { ElMessage } from 'element-plus'
import type { Command } from '@/entities/types'
import { commandStatusClass, commandStatusLabel, useCommand } from '@/features/commands/use-command'
import { api, ApiError } from '@/shared/api/client'

const timestamp = '2026-07-23T08:00:00+00:00'

function command(status: Command['status']): Command {
  return {
    id: 'command-1',
    deviceId: 'device-1',
    commandType: 'manual_control',
    payload: { direction: 'stop', speed: 0 },
    status,
    progress: null,
    result: {},
    routedLinkIds: [],
    linkAcknowledgements: {},
    idempotencyKey: null,
    reasonCode: status === 'rejected' ? 'NO_HEALTHY_ROUTE' : null,
    reasonMessage: status === 'rejected' ? 'No route' : null,
    requiresStateConfirmation: true,
    createdAt: timestamp,
    updatedAt: timestamp,
    expiresAt: timestamp,
    revision: 1
  }
}

describe('command composable', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('shows a device rejection and never invents a success notification', async () => {
    vi.spyOn(api, 'submitCommand').mockResolvedValue(command('rejected'))
    const error = vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    const success = vi.spyOn(ElMessage, 'success').mockImplementation(() => undefined as never)
    const control = useCommand()
    const result = await control.submit('device-1', 'manual_control', {
      direction: 'stop',
      speed: 0
    })
    expect(result?.status).toBe('rejected')
    expect(error).toHaveBeenCalledWith('No route')
    expect(success).not.toHaveBeenCalled()

    vi.spyOn(api, 'submitCommand').mockResolvedValue({
      ...command('rejected'),
      reasonMessage: null
    })
    await control.submit('device-1', 'manual_control', {})
    expect(error).toHaveBeenCalledWith('设备未接受命令')
  })

  it('stores the server command, blocks duplicate submission and maps failures', async () => {
    let resolveCommand: ((value: Command) => void) | undefined
    vi.spyOn(api, 'submitCommand').mockImplementationOnce(
      () => new Promise<Command>((resolve) => (resolveCommand = resolve))
    )
    const errorMessage = vi.spyOn(ElMessage, 'error').mockImplementation(() => undefined as never)
    const control = useCommand()
    const first = control.submit('device-1', 'manual_control', {})
    await expect(control.submit('device-1', 'manual_control', {})).resolves.toBeNull()
    resolveCommand?.(command('completed'))
    await expect(first).resolves.toMatchObject({ status: 'completed' })
    expect(control.lastCommand.value?.status).toBe('completed')

    vi.spyOn(api, 'submitCommand').mockRejectedValueOnce(
      new ApiError(503, 'NO_DRIVER', '驱动不可用')
    )
    await expect(control.submit('device-1', 'manual_control', {})).resolves.toBeNull()
    expect(errorMessage).toHaveBeenCalledWith('驱动不可用')
    vi.spyOn(api, 'submitCommand').mockRejectedValueOnce(new Error('unknown'))
    await control.submit('device-1', 'manual_control', {})
    expect(errorMessage).toHaveBeenCalledWith('命令提交失败')
  })

  it('uses stable labels and visual states for the complete lifecycle', () => {
    expect(commandStatusLabel('queued')).toBe('排队中')
    expect(commandStatusClass('completed')).toBe('success')
    expect(commandStatusClass('rejected')).toBe('danger')
    expect(commandStatusClass('timed_out')).toBe('danger')
    expect(commandStatusClass('state_unconfirmed')).toBe('danger')
    expect(commandStatusClass('accepted')).toBe('active')
    expect(commandStatusClass('in_progress')).toBe('active')
    expect(commandStatusClass('cancelled')).toBe('pending')
  })
})
