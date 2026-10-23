import { ElMessage } from 'element-plus'
import { api } from '@/shared/api/client'
import { streamEventSchema, type StreamEvent } from '@/shared/api/event-schema'
import { runtimeConfig } from '@/shared/config/runtime'
import { useApplicationStore } from '@/app/store'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import { useMissionStore } from '@/entities/mission/store'
import { useTelemetryPresentationStore } from '@/entities/telemetry/presentation-store'

let socket: WebSocket | null = null
let reconnectTimer: number | null = null
let reconnectAttempt = 0
let stopped = true
let refreshPromise: Promise<void> | null = null
let refreshTimer: number | null = null
let lastSequence: number | null = null
let disconnectNoticeShown = false

export async function refreshServerState(): Promise<void> {
  if (refreshPromise) return refreshPromise
  refreshPromise = (async () => {
    const [bootstrap, events, alarms] = await Promise.all([
      api.bootstrap(),
      api.listEvents(500),
      api.listAlarms(false)
    ])
    const fleet = useFleetStore()
    const eventStore = useEventsStore()
    const application = useApplicationStore()
    fleet.applyBootstrap(bootstrap)
    const telemetryPresentation = useTelemetryPresentationStore()
    for (const snapshot of bootstrap.telemetrySnapshots) {
      const activeLinkId = fleet.operationsByDeviceId[snapshot.deviceId]?.activeLinkId
      const latency = activeLinkId
        ? (fleet.sessionsByLinkId[activeLinkId]?.latencyMs ?? null)
        : null
      telemetryPresentation.record(snapshot.deviceId, snapshot, latency, true)
    }
    eventStore.replaceEvents(events)
    eventStore.replaceAlarms(alarms)
    application.settings = bootstrap.settings
  })().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

export async function startDataSource(): Promise<void> {
  stopped = false
  useApplicationStore().setStreamState('connecting')
  try {
    await refreshServerState()
  } catch (error) {
    const message = error instanceof Error ? error.message : '后端初始化失败'
    useFleetStore().setBackendDisconnected(message)
    useApplicationStore().setStreamState('disconnected', message)
  }
  connectStream()
}

export function stopDataSource(): void {
  stopped = true
  if (reconnectTimer != null) window.clearTimeout(reconnectTimer)
  if (refreshTimer != null) window.clearTimeout(refreshTimer)
  reconnectTimer = null
  refreshTimer = null
  const current = socket
  socket = null
  current?.close()
  useFleetStore().setBackendDisconnected()
  useTelemetryPresentationStore().clearRuntime()
  useApplicationStore().setStreamState('disconnected')
}

function connectStream() {
  if (stopped || (socket && socket.readyState < WebSocket.CLOSING)) return
  const fleet = useFleetStore()
  const application = useApplicationStore()
  application.setStreamState('connecting')
  const url = new URL(runtimeConfig.websocketUrl)
  url.searchParams.set('after', String(fleet.eventCursor))
  const next = new WebSocket(url)
  socket = next

  next.onmessage = (message) => {
    if (socket !== next) return
    const parsedJson = parseJson(message.data)
    const parsed = streamEventSchema.safeParse(parsedJson)
    if (!parsed.success) {
      console.error('Rejected invalid server event', parsed.error)
      scheduleRefresh()
      return
    }
    void handleEvent(parsed.data)
  }
  next.onerror = () => {
    if (!disconnectNoticeShown) {
      disconnectNoticeShown = true
      ElMessage.error('后端事件流中断，正在重连')
    }
  }
  next.onclose = () => {
    if (socket !== next) return
    socket = null
    lastSequence = null
    fleet.setBackendDisconnected('后端事件流已断开')
    useTelemetryPresentationStore().clearRuntime()
    application.setStreamState('disconnected', '后端事件流已断开')
    scheduleReconnect()
  }
}

async function handleEvent(event: StreamEvent) {
  const fleet = useFleetStore()
  const application = useApplicationStore()
  if (event.type === 'stream.ready') {
    const instanceChanged =
      fleet.serverInstanceId != null && fleet.serverInstanceId !== event.serverInstanceId
    lastSequence = event.connectionSequence
    if (instanceChanged || event.payload.resyncRequired === true) await refreshServerState()
    reconnectAttempt = 0
    disconnectNoticeShown = false
    application.setStreamState('connected')
    return
  }
  if (event.type === 'stream.heartbeat') return
  if (fleet.serverInstanceId !== event.serverInstanceId) {
    lastSequence = event.connectionSequence
    await refreshServerState()
    return
  }
  if (lastSequence != null && event.connectionSequence !== lastSequence + 1) {
    lastSequence = event.connectionSequence
    await refreshServerState()
    return
  }
  lastSequence = event.connectionSequence
  useEventsStore().recordStreamEvent(event)
  const shouldRefresh = fleet.applyStreamEvent(event)
  useMissionStore().applyStreamEvent(event)
  if (event.type === 'telemetry.updated' || event.type === 'telemetry.quality_changed') {
    const deviceId = event.aggregateId
    const activeLinkId = fleet.operationsByDeviceId[deviceId]?.activeLinkId
    const latency = activeLinkId ? (fleet.sessionsByLinkId[activeLinkId]?.latencyMs ?? null) : null
    useTelemetryPresentationStore().record(deviceId, fleet.telemetryByDeviceId[deviceId], latency)
  }
  if (shouldRefresh) scheduleRefresh()
}

function scheduleRefresh() {
  if (refreshTimer != null) return
  refreshTimer = window.setTimeout(() => {
    refreshTimer = null
    void refreshServerState().catch((error) => console.error('State refresh failed', error))
  }, 100)
}

function scheduleReconnect() {
  if (stopped || reconnectTimer != null) return
  const delay = Math.min(10_000, 500 * 2 ** Math.min(reconnectAttempt, 4))
  reconnectAttempt += 1
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    connectStream()
  }, delay)
}

function parseJson(value: unknown): unknown {
  if (typeof value !== 'string') return null
  try {
    return JSON.parse(value)
  } catch {
    return null
  }
}
