import { apiDelete, apiGet, apiPost, apiPut } from '@/services/http'
import type {
  Alarm,
  ConnectionProfile,
  GoalPoint,
  LogEntry,
  NetworkCandidate,
  Parameter,
  Robot,
  SerialPortInfo
} from '@/types'

export function fetchRobots(): Promise<Robot[]> {
  return apiGet<Robot[]>('/robots')
}

export function fetchLogs(): Promise<LogEntry[]> {
  return apiGet<LogEntry[]>('/logs')
}

export function fetchAlarms(): Promise<Alarm[]> {
  return apiGet<Alarm[]>('/alarms')
}

export function fetchParameters(robotId: string): Promise<Parameter[]> {
  return apiGet<Parameter[]>(`/parameters?robotId=${encodeURIComponent(robotId)}`)
}

export function updateParameters(parameters: Parameter[], robotId: string): Promise<Parameter[]> {
  return apiPut<Parameter[]>('/parameters', { parameters, robotId })
}

export function fetchSerialPorts(): Promise<SerialPortInfo[]> {
  return apiGet<SerialPortInfo[]>('/connections/serial-ports')
}

export function fetchNetworkCandidates(port: number): Promise<NetworkCandidate[]> {
  return apiGet<NetworkCandidate[]>(`/connections/network-candidates?port=${encodeURIComponent(port)}`)
}

export function connectRobot(robotId: string, profile: ConnectionProfile): Promise<Robot> {
  return apiPost<Robot>(`/robots/${encodeURIComponent(robotId)}/connection`, profile)
}

export function disconnectRobot(robotId: string): Promise<Robot> {
  return apiDelete<Robot>(`/robots/${encodeURIComponent(robotId)}/connection`)
}

export function postManualCommand(robotId: string, command: string, speed: number, speedGear?: string): Promise<Robot> {
  return apiPost<Robot>('/commands/manual', { robotId, command, speed, speedGear })
}

export function postModeCommand(robotId: string, mode: '手动' | '自动'): Promise<Robot> {
  return apiPost<Robot>('/commands/mode', { robotId, mode })
}

export function postLockCommand(robotId: string, unlocked: boolean): Promise<Robot> {
  return apiPost<Robot>('/commands/lock', { robotId, unlocked })
}

export function postEmergencyStop(robotId: string): Promise<Robot> {
  return apiPost<Robot>('/commands/emergency-stop', { robotId })
}

export function postElectromagneticFix(robotId: string, enabled: boolean): Promise<Robot> {
  return apiPost<Robot>('/commands/electromagnetic-fix', { robotId, enabled })
}

export function postNavigationStart(robotId: string, goals: GoalPoint[]): Promise<Robot> {
  return apiPost<Robot>('/commands/navigation/start', { robotId, goals })
}

export function postNavigationPause(robotId: string): Promise<Robot> {
  return apiPost<Robot>('/commands/navigation/pause', { robotId })
}

export function postNavigationResume(robotId: string): Promise<Robot> {
  return apiPost<Robot>('/commands/navigation/resume', { robotId })
}

export function postNavigationStop(robotId: string): Promise<Robot> {
  return apiPost<Robot>('/commands/navigation/stop', { robotId })
}

export function postNavigationReturnHome(robotId: string): Promise<Robot> {
  return apiPost<Robot>('/commands/navigation/return-home', { robotId })
}
