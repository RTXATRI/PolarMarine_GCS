import type { ConnectionRuntime, Robot } from '../../src/types'

export const disconnectedRuntime: ConnectionRuntime = {
  state: 'disconnected',
  activeMethod: null,
  endpoint: null,
  dataMode: 'none',
  commandMode: 'none',
  connectedAt: null,
  error: null
}

export function makeRobot(id: string, connection: Partial<ConnectionRuntime> = {}): Robot {
  const runtime: ConnectionRuntime = { ...disconnectedRuntime, ...connection }
  const hasVirtualData = runtime.state === 'connected' && runtime.dataMode === 'virtual'
  return {
    id,
    robotType: 'uav',
    online: runtime.state === 'connected',
    connectionProfile: null,
    connection: runtime,
    battery: hasVirtualData ? 80 : null,
    mode: hasVirtualData ? '手动' : null,
    px4Mode: null,
    missionStatus: hasVirtualData ? '空闲' : null,
    linkStatus: hasVirtualData ? '正常' : null,
    latencyMs: hasVirtualData ? 50 : null,
    packetLoss: hasVirtualData ? 0 : null,
    rssi: hasVirtualData ? -50 : null,
    position: hasVirtualData ? { lat: 30, lon: 120 } : null,
    altitude: hasVirtualData ? 10 : null,
    speed: hasVirtualData ? 0 : null,
    heading: hasVirtualData ? 0 : null,
    alarm: null,
    trail: [],
    lastCommAt: hasVirtualData ? new Date().toISOString() : null,
    unlocked: hasVirtualData ? false : null,
    relayEnabled: null,
    maxSpeed: 1,
    homePosition: hasVirtualData ? { lat: 30, lon: 120 } : null,
    navState: 'idle',
    navGoals: [],
    navGoalIndex: 0,
    wobbleAnchor: hasVirtualData ? { lat: 30, lon: 120 } : null
  }
}
