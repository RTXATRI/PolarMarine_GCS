import type { ConnectionState, Robot } from '@/types'

export function isRobotConnected(robot: Robot | null | undefined): boolean {
  return robot?.connection.state === 'connected'
}

export function hasUsableDataChannel(robot: Robot | null | undefined): boolean {
  return isRobotConnected(robot) && robot?.connection.dataMode !== 'none'
}

export function hasCommandChannel(robot: Robot | null | undefined): boolean {
  return isRobotConnected(robot) && robot?.connection.commandMode !== 'none'
}

export function connectionStateText(state: ConnectionState): string {
  if (state === 'connected') return '已连接'
  if (state === 'connecting') return '连接中'
  if (state === 'error') return '连接失败'
  return '未连接'
}

export function connectionTone(state: ConnectionState): 'online' | 'warn' | 'danger' | 'offline' {
  if (state === 'connected') return 'online'
  if (state === 'connecting') return 'warn'
  if (state === 'error') return 'danger'
  return 'offline'
}

export function connectionMethodText(robot: Robot | null | undefined): string {
  if (!isRobotConnected(robot)) return '未知'
  if (robot?.connection.activeMethod === 'serial') return '串口'
  if (robot?.connection.activeMethod === 'network') return '网络'
  return '未知'
}
