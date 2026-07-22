import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type { ConnectionRuntime, Robot, RobotId } from '@/types'

const DISCONNECTED_RUNTIME: ConnectionRuntime = {
  state: 'disconnected',
  activeMethod: null,
  endpoint: null,
  dataMode: 'none',
  commandMode: 'none',
  connectedAt: null,
  error: null
}

function normalizeRobot(robot: Robot): Robot {
  const connection = robot.connection ?? { ...DISCONNECTED_RUNTIME }
  const normalizedConnection: ConnectionRuntime = {
    ...connection,
    commandMode: connection.commandMode ?? (connection.dataMode === 'virtual' ? 'virtual' : 'none')
  }
  return {
    ...robot,
    connection: normalizedConnection,
    px4Mode: robot.px4Mode ?? null,
    connectionProfile: robot.connectionProfile ?? null,
    // online is retained only for compatibility with older view code. The
    // connection state is always authoritative.
    online: normalizedConnection.state === 'connected'
  }
}

export const useRobotsStore = defineStore('robots', () => {
  // The backend owns the registry. An empty list is intentional while it is
  // unavailable; never seed this store from the frontend mock catalogue.
  const robots = ref<Robot[]>([])
  const selectedId = ref<RobotId>('')

  const selected = computed(() => robots.value.find(robot => robot.id === selectedId.value) ?? null)
  const connectedCount = computed(() => robots.value.filter(robot => robot.connection.state === 'connected').length)
  const onlineCount = connectedCount
  const sortedRobots = computed(() => robots.value
    .map((robot, index) => ({ robot, index }))
    .sort((a, b) => {
      const rank = (state: Robot['connection']['state']) => state === 'connected' ? 0 : state === 'connecting' ? 1 : 2
      return rank(a.robot.connection.state) - rank(b.robot.connection.state) || a.index - b.index
    })
    .map(item => item.robot))

  function getById(id: RobotId): Robot | undefined {
    return robots.value.find(robot => robot.id === id)
  }

  function replaceAll(next: Robot[]) {
    robots.value = next.map(normalizeRobot)
    if (!robots.value.some(robot => robot.id === selectedId.value)) {
      selectedId.value = robots.value[0]?.id ?? ''
    }
  }

  function applyRobot(next: Robot) {
    const normalized = normalizeRobot(next)
    const index = robots.value.findIndex(robot => robot.id === normalized.id)
    if (index === -1) robots.value.push(normalized)
    else robots.value[index] = normalized
    if (!selectedId.value) selectedId.value = normalized.id
  }

  function select(id: RobotId): boolean {
    if (selectedId.value === id) return false
    if (!robots.value.some(robot => robot.id === id)) return false
    selectedId.value = id
    return true
  }

  return {
    robots,
    sortedRobots,
    selectedId,
    selected,
    connectedCount,
    onlineCount,
    getById,
    replaceAll,
    applyRobot,
    select
  }
})
