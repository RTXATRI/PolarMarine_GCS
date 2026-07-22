import type { Robot } from '@/types'

export interface MapCenter {
  lat: number
  lon: number
}

export const DEFAULT_MAP_CENTER: MapCenter = { lat: 30.3168, lon: 120.3505 }

function connectedWithPosition(robot: Robot | undefined): robot is Robot {
  return robot?.connection.state === 'connected' && robot.position != null
}

export function resolveInitialMapCenter(
  sortedRobots: Robot[],
  selectedId: string,
  backendConnected: boolean
): MapCenter {
  if (!backendConnected) return { ...DEFAULT_MAP_CENTER }

  const selected = sortedRobots.find(robot => robot.id === selectedId)
  const target = connectedWithPosition(selected)
    ? selected
    : sortedRobots.find(robot => connectedWithPosition(robot))

  return target?.position ? { ...target.position } : { ...DEFAULT_MAP_CENTER }
}
