// 全局类型定义

export type RobotId = string

export type ControlMode = '手动' | '自动' | '离线' | '急停'

export type LinkStatus = '正常' | '延迟高' | '丢包' | '断开'

export type DeviceType = 'uav' | 'usv' | 'dock'

export type NavState = 'idle' | 'navigating' | 'paused' | 'returning_home'

export type MissionStatus =
  | '空闲'
  | '正在前往目标点'
  | '导航中'
  | '巡航中'
  | '返航中'
  | '暂停'
  | '急停'
  | '无任务'

export type LogType = '操作' | '通信' | '报警' | '系统'

export type AlarmLevel = '提示' | '警告' | '严重'

export type ConnectionState = 'disconnected' | 'connecting' | 'connected' | 'error'

export type ConnectionMethod = 'serial' | 'network'

export type DataMode = 'none' | 'virtual' | 'live'

export type CommandMode = 'none' | 'virtual' | 'live'

export type ConnectionProfile =
  | { method: 'serial'; port: string; baudRate: number }
  | { method: 'network'; host: string; port: number }

export interface ConnectionError {
  code: string
  message: string
}

export interface ConnectionRuntime {
  state: ConnectionState
  activeMethod: ConnectionMethod | null
  endpoint: string | null
  dataMode: DataMode
  commandMode: CommandMode
  connectedAt: string | null
  error: ConnectionError | null
}

export interface SerialPortInfo {
  port: string
  description: string
  manufacturer?: string | null
  hwid?: string | null
}

export interface NetworkCandidate {
  host: string
  hostname?: string | null
  port: number
  latencyMs?: number | null
}

export interface Robot {
  id: RobotId
  /** 设备类型 */
  robotType: DeviceType
  /** 兼容字段，只能由 connection.state 派生。 */
  online: boolean
  connectionProfile: ConnectionProfile | null
  connection: ConnectionRuntime
  /** null 表示未知 */
  battery: number | null
  mode: ControlMode | null
  /** PX4/MAVROS 上报的原始飞行模式，例如 POSCTL。 */
  px4Mode: string | null
  missionStatus: MissionStatus | null
  linkStatus: LinkStatus | null
  /** 单位 ms,null 表示 -- */
  latencyMs: number | null
  /** 0~100,null 表示 -- */
  packetLoss: number | null
  /** 单位 dBm,null 表示 -- */
  rssi: number | null
  /** 经纬度,null 表示未知 */
  position: { lat: number; lon: number } | null
  /** 海拔,单位 m,null 表示未知 */
  altitude: number | null
  /** 单位 m/s,null 表示 -- */
  speed: number | null
  /** 当前航向角,度,null 表示未知 */
  heading: number | null
  alarm: string | null
  /** 历史轨迹 */
  trail: Array<{ lat: number; lon: number }>
  /** 最后通信时间,ISO 字符串 */
  lastCommAt: string | null
  /** 是否解锁(用于手动控制) */
  unlocked: boolean | null
  /** CL-USV 电磁固定继电器的真实反馈状态。 */
  relayEnabled: boolean | null

  /** 最大速度 m/s，由参数配置控制 */
  maxSpeed: number
  /** 初始/归位点 */
  homePosition: { lat: number; lon: number } | null
  /** 导航状态机 */
  navState: NavState
  /** 已下发的导航目标点 */
  navGoals: GoalPoint[]
  /** 当前正在前往的目标索引 */
  navGoalIndex: number
  /** 定点维持的锚点位置 */
  wobbleAnchor: { lat: number; lon: number } | null
}

export interface TelemetryMsg {
  id: number
  time: string // ISO
  robotId: RobotId
  /** 键值对，如 { 速度: '0.52 m/s', 坐标: '30.3105, 120.3451', 电量: '78%' } */
  fields: Record<string, string>
}

export interface LogEntry {
  id: number
  time: string // ISO
  type: LogType
  robotId: RobotId | null
  content: string
}

export interface Alarm {
  id: number
  time: string
  level: AlarmLevel
  robotId: RobotId
  content: string
  acknowledged: boolean
}

export interface Parameter {
  key: string
  name: string
  /** 当前生效值 */
  currentValue: number
  /** 用户在表格中输入的待写入值 */
  editValue: number
  unit: string
  description: string
  /** 默认值,用于"恢复默认" */
  defaultValue: number
}

export interface Waypoint {
  index: number
  lat: number
  lon: number
  speed: number
}

export interface GoalPoint {
  id: string
  lat: number
  lon: number
  speed: number
}
