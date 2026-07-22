import { ElMessage } from 'element-plus'
import { runtimeConfig } from '@/config/runtime'
import { fetchAlarms, fetchLogs, fetchRobots } from '@/services/backend-api'
import { useLogsStore } from '@/stores/logs'
import { useRobotsStore } from '@/stores/robots'
import { useSystemStore } from '@/stores/system'
import { useTrendsStore } from '@/stores/trends'
import type { Alarm, LogEntry, Robot, TelemetryMsg } from '@/types'

type BackendMessage =
  | { type: 'robot_state'; data: Robot[] }
  | { type: 'log_snapshot'; data: LogEntry[] }
  | { type: 'alarm_snapshot'; data: Alarm[] }
  | { type: 'log'; data: LogEntry }
  | { type: 'alarm'; data: Alarm }
  | { type: 'telemetry'; data: TelemetryMsg }
  | { type: 'rosbridge_status'; data: { connected: boolean } }

let socket: WebSocket | null = null
let reconnectTimer: number | null = null
let reconnectAttempt = 0
let stopped = false
let connectionErrorShown = false
let initializationPromise: Promise<void> | null = null

export async function initializeBackendData(): Promise<void> {
  const robots = useRobotsStore()
  const logs = useLogsStore()
  const [robotData, logData, alarmData] = await Promise.all([fetchRobots(), fetchLogs(), fetchAlarms()])
  robots.replaceAll(robotData)
  logs.replaceLogs(logData)
  logs.replaceAlarms(alarmData)
}

function scheduleReconnect() {
  if (stopped || reconnectTimer !== null) return
  const delay = Math.min(10_000, 1_000 * 2 ** Math.min(reconnectAttempt, 3))
  reconnectAttempt += 1
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = null
    connectBackendStream()
  }, delay)
}

export function connectBackendStream(): void {
  if (socket && socket.readyState !== WebSocket.CLOSED) return

  const robots = useRobotsStore()
  const logs = useLogsStore()
  const system = useSystemStore()
  const trends = useTrendsStore()
  stopped = false
  system.setBackendState('connecting')

  const nextSocket = new WebSocket(runtimeConfig.wsUrl)
  socket = nextSocket

  nextSocket.onopen = () => {
    if (socket !== nextSocket) return
    // The socket being open does not make the cached robot snapshot current.
    // Keep the UI gated until this exact connection delivers its first state.
    system.setBackendState('connecting')
  }

  nextSocket.onmessage = (event) => {
    if (socket !== nextSocket) return
    try {
      const message = JSON.parse(event.data) as BackendMessage
      if (message.type === 'robot_state') {
        robots.replaceAll(message.data)
        trends.recordSnapshot(robots.robots)
        reconnectAttempt = 0
        connectionErrorShown = false
        system.setBackendState('connected')
      }
      else if (message.type === 'log_snapshot') logs.replaceLogs(message.data)
      else if (message.type === 'alarm_snapshot') logs.replaceAlarms(message.data)
      else if (message.type === 'log') logs.applyLog(message.data)
      else if (message.type === 'alarm') logs.applyAlarm(message.data)
      else if (message.type === 'telemetry') logs.applyTelemetry(message.data)
    } catch (error) {
      console.error('Invalid backend WebSocket message:', error)
    }
  }

  nextSocket.onerror = () => {
    // onclose owns retry and state transitions. Avoid one toast per attempt.
    if (!connectionErrorShown) {
      connectionErrorShown = true
      ElMessage.error('后端连接中断，正在自动重连')
    }
  }

  nextSocket.onclose = () => {
    if (socket !== nextSocket) return
    socket = null
    trends.clearAll()
    system.setBackendState('disconnected', '后端 WebSocket 已断开')
    scheduleReconnect()
  }
}

export function startBackendDataSource(): Promise<void> {
  if (initializationPromise) return initializationPromise

  initializationPromise = (async () => {
    const system = useSystemStore()
    system.setBackendState('connecting')
    try {
      await initializeBackendData()
    } catch (error) {
      system.setBackendState('disconnected', error instanceof Error ? error.message : '后端初始化失败')
      console.error('GCS backend initialization failed:', error)
    } finally {
      connectBackendStream()
      initializationPromise = null
    }
  })()
  return initializationPromise
}

export function disconnectBackendStream(): void {
  stopped = true
  if (reconnectTimer !== null) {
    window.clearTimeout(reconnectTimer)
    reconnectTimer = null
  }
  const current = socket
  socket = null
  current?.close()
  useTrendsStore().clearAll()
  useSystemStore().setBackendState('disconnected')
}
