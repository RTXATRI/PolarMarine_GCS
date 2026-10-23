import type {
  DriverKind,
  LinkSessionState,
  OperationalStatus,
  TelemetryValue
} from '@/entities/types'

const operationalLabels: Record<OperationalStatus, string> = {
  offline: '离线',
  online: '在线',
  degraded: '降级',
  failing_over: '切换中'
}

const sessionLabels: Record<LinkSessionState, string> = {
  stopped: '已停止',
  starting: '启动中',
  handshaking: '身份握手',
  healthy: '健康',
  degraded: '降级',
  recovering: '恢复中',
  failed: '失败'
}

const driverLabels: Record<DriverKind, string> = {
  ros1: 'ROS 1',
  ros2: 'ROS 2',
  serial_json: '串口 JSON',
  simulator: '显式仿真'
}

const telemetryLabels: Record<string, string> = {
  'position.latitude': '纬度',
  'position.longitude': '经度',
  'position.altitude': '高度',
  'battery.percent': '电量',
  speed: '速度',
  heading: '航向',
  'control.mode': '控制模式',
  'control.armed': '解锁状态',
  'mission.status': '任务状态'
}

export const operationalLabel = (value: OperationalStatus): string => operationalLabels[value]
export const sessionLabel = (value: LinkSessionState): string => sessionLabels[value]
export const driverLabel = (value: DriverKind): string => driverLabels[value]
export const telemetryLabel = (key: string): string => telemetryLabels[key] ?? key

export function statusTone(
  status: OperationalStatus
): 'neutral' | 'success' | 'warning' | 'danger' {
  if (status === 'online') return 'success'
  if (status === 'degraded' || status === 'failing_over') return 'warning'
  return 'neutral'
}

export function formatTelemetry(value: TelemetryValue | undefined): string {
  if (!value || value.value == null || value.quality === 'invalid' || value.quality === 'unknown')
    return '无效'
  if (value.quality === 'stale') return '已过期'
  const raw =
    typeof value.value === 'number'
      ? Number.isInteger(value.value)
        ? String(value.value)
        : value.value.toFixed(3)
      : String(value.value)
  return raw + (value.unit ? ' ' + value.unit : '')
}

export function formatTime(value: string | null | undefined): string {
  if (!value) return '--'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '--' : date.toLocaleString('zh-CN', { hour12: false })
}

export function eventLabel(type: string): string {
  const labels: Record<string, string> = {
    'catalogue.seeded': '设备目录初始化',
    'link_session.changed': '链路状态变化',
    'device.route_changed': '主链路切换',
    'command.changed': '命令状态变化',
    'alarm.raised': '产生告警',
    'alarm.acknowledged': '告警已确认',
    'mission_run.changed': '任务运行变化',
    'parameters.confirmed': '参数写入确认'
  }
  return labels[type] ?? type
}
