import { runtimeConfig } from '@/shared/config/runtime'
import type {
  Alarm,
  AsyncOperationReceipt,
  Bootstrap,
  Command,
  CommandRequest,
  Device,
  DeviceTemplate,
  DeviceTemplateWrite,
  DeviceWrite,
  LinkProfile,
  LinkProfileWrite,
  MissionPlan,
  MissionPlanWrite,
  MissionRun,
  NetworkDiscoveryResponse,
  ParameterState,
  PersistedEvent,
  Recording,
  RecordingMessage,
  RosDebugRequest
} from '@/entities/types'

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: Record<string, unknown>

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {}
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(runtimeConfig.apiBase + path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers
    }
  })
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as {
      error?: { code?: string; message?: string; details?: Record<string, unknown> }
    } | null
    throw new ApiError(
      response.status,
      body?.error?.code ?? 'HTTP_ERROR',
      body?.error?.message ?? 'HTTP ' + response.status,
      body?.error?.details
    )
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

const json = (value: unknown): string => JSON.stringify(value)

export const api = {
  bootstrap: (): Promise<Bootstrap> => request('/bootstrap'),
  listTemplates: (): Promise<DeviceTemplate[]> => request('/device-templates'),
  listDevices: (): Promise<Device[]> => request('/devices'),
  createTemplate: (body: DeviceTemplateWrite): Promise<DeviceTemplate> =>
    request('/device-templates', { method: 'POST', body: json(body) }),
  updateTemplate: (id: string, body: DeviceTemplateWrite): Promise<DeviceTemplate> =>
    request('/device-templates/' + encodeURIComponent(id), { method: 'PUT', body: json(body) }),
  deleteTemplate: (id: string): Promise<void> =>
    request('/device-templates/' + encodeURIComponent(id), { method: 'DELETE' }),
  createDevice: (body: DeviceWrite): Promise<Device> =>
    request('/devices', { method: 'POST', body: json(body) }),
  updateDevice: (id: string, body: DeviceWrite): Promise<Device> =>
    request('/devices/' + encodeURIComponent(id), { method: 'PUT', body: json(body) }),
  deleteDevice: (id: string): Promise<void> =>
    request('/devices/' + encodeURIComponent(id), { method: 'DELETE' }),
  listLinks: (deviceId: string): Promise<LinkProfile[]> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/links'),
  createLink: (deviceId: string, body: LinkProfileWrite): Promise<LinkProfile> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/links', {
      method: 'POST',
      body: json(body)
    }),
  updateLink: (deviceId: string, linkId: string, body: LinkProfileWrite): Promise<LinkProfile> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/links/' + encodeURIComponent(linkId), {
      method: 'PUT',
      body: json(body)
    }),
  deleteLink: (deviceId: string, linkId: string): Promise<void> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/links/' + encodeURIComponent(linkId), {
      method: 'DELETE'
    }),
  connectLink: (deviceId: string, linkId: string): Promise<AsyncOperationReceipt> =>
    request(
      '/devices/' +
        encodeURIComponent(deviceId) +
        '/links/' +
        encodeURIComponent(linkId) +
        '/connect',
      { method: 'POST' }
    ),
  disconnectLink: (deviceId: string, linkId: string): Promise<AsyncOperationReceipt> =>
    request(
      '/devices/' +
        encodeURIComponent(deviceId) +
        '/links/' +
        encodeURIComponent(linkId) +
        '/disconnect',
      { method: 'POST' }
    ),
  submitCommand: (deviceId: string, body: CommandRequest): Promise<Command> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/commands', {
      method: 'POST',
      body: json(body)
    }),
  getCommand: (commandId: string): Promise<Command> =>
    request('/commands/' + encodeURIComponent(commandId)),
  listEvents: (limit = 200): Promise<PersistedEvent[]> => request('/events?limit=' + limit),
  listAlarms: (activeOnly = false): Promise<Alarm[]> => request('/alarms?activeOnly=' + activeOnly),
  acknowledgeAlarm: (alarmId: string): Promise<Alarm> =>
    request('/alarms/' + encodeURIComponent(alarmId) + '/acknowledge', { method: 'POST' }),
  listParameters: (deviceId: string): Promise<ParameterState[]> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/parameters'),
  refreshParameters: (deviceId: string): Promise<Command> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/parameters/read', { method: 'POST' }),
  writeParameters: (deviceId: string, values: Record<string, unknown>): Promise<Command> =>
    request('/devices/' + encodeURIComponent(deviceId) + '/parameters', {
      method: 'PUT',
      body: json({ values })
    }),
  listMissions: (): Promise<MissionPlan[]> => request('/missions'),
  listMissionVersions: (id: string): Promise<MissionPlan[]> =>
    request('/missions/' + encodeURIComponent(id) + '/versions'),
  createMission: (body: MissionPlanWrite): Promise<MissionPlan> =>
    request('/missions', { method: 'POST', body: json(body) }),
  updateMission: (id: string, body: MissionPlanWrite): Promise<MissionPlan> =>
    request('/missions/' + encodeURIComponent(id), { method: 'PUT', body: json(body) }),
  deleteMission: (id: string): Promise<void> =>
    request('/missions/' + encodeURIComponent(id), { method: 'DELETE' }),
  listMissionRuns: (): Promise<MissionRun[]> => request('/mission-runs'),
  startMission: (id: string): Promise<MissionRun> =>
    request('/missions/' + encodeURIComponent(id) + '/runs', { method: 'POST' }),
  controlMission: (
    runId: string,
    action: 'pause' | 'resume' | 'cancel'
  ): Promise<{ missionRunId: string; commands: Command[] }> =>
    request('/mission-runs/' + encodeURIComponent(runId) + '/' + action, { method: 'POST' }),
  listRecordings: (): Promise<Recording[]> => request('/recordings'),
  recordingMessages: (recordingId: string, limit = 1_000): Promise<RecordingMessage[]> =>
    request('/recordings/' + encodeURIComponent(recordingId) + '/messages?limit=' + limit),
  recordingDownloadUrl: (recordingId: string): string =>
    runtimeConfig.apiBase + '/recordings/' + encodeURIComponent(recordingId) + '/download',
  supportBundleUrl: (): string => runtimeConfig.apiBase + '/support-bundle',
  rosDebug: (body: RosDebugRequest): Promise<Record<string, unknown>> =>
    request('/debug/ros', { method: 'POST', body: json(body) }),
  serialPorts: (): Promise<{ ok: boolean; ports?: Array<Record<string, unknown>> }> =>
    request('/debug/serial/ports'),
  discoverNetwork: (
    driver: 'ros1' | 'ros2',
    timeoutSeconds = 1.5
  ): Promise<NetworkDiscoveryResponse> =>
    request('/discovery/network?driver=' + driver + '&timeoutSeconds=' + timeoutSeconds)
}
