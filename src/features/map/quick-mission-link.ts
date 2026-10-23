const STORAGE_KEY = 'polarmarine-gcs-map-quick-missions-v1'

function readMappings(): Record<string, string> {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? '{}')
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return {}
    return Object.fromEntries(
      Object.entries(parsed).filter(
        (entry): entry is [string, string] =>
          typeof entry[0] === 'string' && typeof entry[1] === 'string'
      )
    )
  } catch {
    return {}
  }
}

export function readQuickMissionId(deviceId: string): string | null {
  return readMappings()[deviceId] ?? null
}

export function writeQuickMissionId(deviceId: string, missionPlanId: string | null): void {
  try {
    const mappings = readMappings()
    if (missionPlanId) mappings[deviceId] = missionPlanId
    else delete mappings[deviceId]
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(mappings))
  } catch {
    // The persisted MissionPlan remains authoritative even if local storage is unavailable.
  }
}

export function quickMissionDescription(deviceId: string): string {
  return `[map-quick:v1:${deviceId}] 由地图页维护的快捷任务，可在任务页继续编辑和执行。`
}

export function isQuickMissionForDevice(description: string, deviceId: string): boolean {
  return description.includes(`[map-quick:v1:${deviceId}]`)
}
