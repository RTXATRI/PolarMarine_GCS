import type {
  Device,
  DeviceTemplate,
  LinkProfile,
  LinkSession,
  OperationalState,
  TelemetrySnapshot,
  TelemetryValue
} from '@/entities/types'
import { formatTelemetry } from '@/shared/lib/presentation'

export type UiTone = 'online' | 'offline' | 'warn' | 'danger' | 'info' | 'muted' | 'simulation'

const categoryLabels: Record<DeviceTemplate['category'], string> = {
  aerial: '无人机',
  surface: '无人船',
  station: '固定站',
  generic: '通用设备'
}

export function categoryLabel(category: DeviceTemplate['category'] | undefined): string {
  return category ? categoryLabels[category] : '未知类型'
}

export function operationTone(status: OperationalState['status'] | undefined): UiTone {
  if (status === 'online') return 'online'
  if (status === 'degraded' || status === 'failing_over') return 'warn'
  return 'offline'
}

export function operationText(status: OperationalState['status'] | undefined): string {
  if (status === 'online') return '在线'
  if (status === 'degraded') return '降级'
  if (status === 'failing_over') return '链路切换中'
  return '离线'
}

export function linkStateTone(state: LinkSession['state'] | undefined): UiTone {
  if (state === 'healthy') return 'online'
  if (state === 'failed') return 'danger'
  if (state === 'stopped' || state == null) return 'offline'
  return 'warn'
}

export function validTelemetryValue(
  snapshot: TelemetrySnapshot | null | undefined,
  key: string
): TelemetryValue | undefined {
  const value = snapshot?.fields[key]
  return value && value.value != null && !['invalid', 'unknown', 'stale'].includes(value.quality)
    ? value
    : undefined
}

export function numericTelemetry(
  snapshot: TelemetrySnapshot | null | undefined,
  key: string
): number | null {
  const value = validTelemetryValue(snapshot, key)?.value
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export function textTelemetry(
  snapshot: TelemetrySnapshot | null | undefined,
  key: string,
  fallback = '未知'
): string {
  const value = snapshot?.fields[key]
  const formatted = formatTelemetry(value)
  return formatted === '无效' || formatted === '已过期' ? fallback : formatted
}

export function valueText(
  snapshot: TelemetrySnapshot | null | undefined,
  key: string,
  fallback = '--'
): string {
  const value = snapshot?.fields[key]
  if (!value) return fallback
  return formatTelemetry(value)
}

export function isSimulatorRoute(
  operation: OperationalState | null | undefined,
  linksById: Record<string, LinkProfile>
): boolean {
  return Boolean(
    operation?.activeLinkId && linksById[operation.activeLinkId]?.driver === 'simulator'
  )
}

export function hasCapability(
  template: DeviceTemplate | null | undefined,
  capability: string
): boolean {
  return Boolean(template?.capabilities?.includes(capability))
}

export function deviceSearchText(device: Device, template: DeviceTemplate | undefined): string {
  return [
    device.id,
    device.displayName,
    device.description,
    template?.displayName,
    ...(device.tags ?? [])
  ]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase('zh-CN')
}
