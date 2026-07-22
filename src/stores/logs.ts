import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { Alarm, AlarmLevel, LogEntry, LogType, RobotId, TelemetryMsg } from '@/types'
import { toUserFacingOperationText } from '@/utils/user-facing-text'

const MAX_LOGS = 500
const MAX_TELEMETRY_PER_ROBOT = 200

export const useLogsStore = defineStore('logs', () => {
  const logs = ref<LogEntry[]>([])
  const alarms = ref<Alarm[]>([])
  // Client-only entries use negative IDs so they can never overwrite the
  // backend's positive, authoritative sequence numbers.
  let localLogSeq = -1
  let localAlarmSeq = -1

  const recent = computed(() => logs.value.slice(0, 8))
  const activeAlarms = computed(() => alarms.value.filter(a => !a.acknowledged))

  function syncSeq() {
    // Kept as a named hook because replace/apply callers share this path.
    // Backend IDs do not influence the separate negative local sequence.
  }

  function replaceLogs(next: LogEntry[]) {
    logs.value = next.map(toUserFacingLog)
    syncSeq()
  }

  function replaceAlarms(next: Alarm[]) {
    alarms.value = next.map(toUserFacingAlarm)
    syncSeq()
  }

  function applyLog(entry: LogEntry) {
    const displayedEntry = toUserFacingLog(entry)
    const existing = logs.value.findIndex(l => l.id === displayedEntry.id)
    if (existing === -1) {
      logs.value.unshift(displayedEntry)
    } else {
      logs.value[existing] = displayedEntry
    }
    if (logs.value.length > MAX_LOGS) logs.value.length = MAX_LOGS
    syncSeq()
  }

  function applyAlarm(alarm: Alarm) {
    const displayedAlarm = toUserFacingAlarm(alarm)
    const existing = alarms.value.findIndex(a => a.id === displayedAlarm.id)
    if (existing === -1) {
      alarms.value.unshift(displayedAlarm)
    } else {
      alarms.value[existing] = displayedAlarm
    }
    syncSeq()
  }

  function append(type: LogType, robotId: RobotId | null, content: string) {
    const entry: LogEntry = {
      id: localLogSeq--,
      time: new Date().toISOString(),
      type,
      robotId,
      content: toUserFacingOperationText(content)
    }
    logs.value.unshift(entry)
    if (logs.value.length > MAX_LOGS) logs.value.length = MAX_LOGS
    return entry
  }

  function pushAlarm(level: AlarmLevel, robotId: RobotId, content: string) {
    const a: Alarm = {
      id: localAlarmSeq--,
      time: new Date().toISOString(),
      level,
      robotId,
      content: toUserFacingOperationText(content),
      acknowledged: false
    }
    alarms.value.unshift(a)
    append('报警', robotId, content)
    return a
  }

  function ackAlarm(id: number) {
    const a = alarms.value.find(x => x.id === id)
    if (a) a.acknowledged = true
  }

  function ackAll() {
    alarms.value.forEach(a => (a.acknowledged = true))
  }

  function clearLogs() {
    logs.value = []
    append('系统', null, '历史日志已清空')
  }

  function clearAlarms() {
    alarms.value = []
  }

  function filtered(opts: { robotId?: RobotId | null; type?: LogType | null }): LogEntry[] {
    return logs.value.filter(l => {
      if (opts.robotId && l.robotId !== opts.robotId) return false
      if (opts.type && l.type !== opts.type) return false
      return true
    })
  }

  // ─── 遥测消息 ───

  const telemetryMsgs = ref<Map<RobotId, TelemetryMsg[]>>(new Map())
  let telemSeq = 0

  function pushTelemetry(robotId: RobotId, fields: Record<string, string>) {
    const msg: TelemetryMsg = { id: telemSeq++, time: new Date().toISOString(), robotId, fields }
    const arr = telemetryMsgs.value.get(robotId) ?? []
    arr.push(msg)
    if (arr.length > MAX_TELEMETRY_PER_ROBOT) arr.splice(0, arr.length - MAX_TELEMETRY_PER_ROBOT)
    telemetryMsgs.value.set(robotId, arr)
  }

  function applyTelemetry(msg: TelemetryMsg) {
    const arr = telemetryMsgs.value.get(msg.robotId) ?? []
    const existing = arr.findIndex(item => item.id === msg.id)
    if (existing === -1) {
      arr.push(msg)
    } else {
      arr[existing] = msg
    }
    if (arr.length > MAX_TELEMETRY_PER_ROBOT) arr.splice(0, arr.length - MAX_TELEMETRY_PER_ROBOT)
    telemetryMsgs.value.set(msg.robotId, arr)
    telemSeq = Math.max(telemSeq, msg.id + 1)
  }

  function getTelemetry(robotId: RobotId): TelemetryMsg[] {
    return telemetryMsgs.value.get(robotId) ?? []
  }

  function toUserFacingLog(entry: LogEntry): LogEntry {
    return { ...entry, content: toUserFacingOperationText(entry.content) }
  }

  function toUserFacingAlarm(alarm: Alarm): Alarm {
    return { ...alarm, content: toUserFacingOperationText(alarm.content) }
  }

  return {
    logs,
    alarms,
    recent,
    activeAlarms,
    replaceLogs,
    replaceAlarms,
    applyLog,
    applyAlarm,
    append,
    pushAlarm,
    ackAlarm,
    ackAll,
    clearLogs,
    clearAlarms,
    filtered,
    telemetryMsgs,
    pushTelemetry,
    applyTelemetry,
    getTelemetry
  }
})
