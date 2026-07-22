import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Robot } from '@/types'

/** 每台设备最近 60 个秒级趋势采样点。 */
interface TrendBuffer {
  battery: number[]
  latency: number[]
  speed: number[]
}

const MAX_TREND_POINTS = 60

function emptyBuffer(): TrendBuffer {
  return { battery: [], latency: [], speed: [] }
}

function appendLimited(target: number[], value: number | null): boolean {
  if (value === null || !Number.isFinite(value)) return false
  target.push(value)
  if (target.length > MAX_TREND_POINTS) target.shift()
  return true
}

export const useTrendsStore = defineStore('trends', () => {
  const buffers = ref<Record<string, TrendBuffer>>({})
  let lastSampleSecond: Record<string, number> = {}

  function ensure(id: string): TrendBuffer {
    let buffer = buffers.value[id]
    if (!buffer) {
      buffer = emptyBuffer()
      buffers.value[id] = buffer
    }
    return buffer
  }

  function clear(id: string) {
    delete buffers.value[id]
    delete lastSampleSecond[id]
  }

  function clearAll() {
    buffers.value = {}
    lastSampleSecond = {}
  }

  function recordSnapshot(robots: Robot[], timestamp = Date.now()) {
    const snapshotIds = new Set(robots.map(robot => robot.id))
    for (const id of Object.keys(buffers.value)) {
      if (!snapshotIds.has(id)) clear(id)
    }

    const sampleSecond = Math.floor(timestamp / 1000)
    for (const robot of robots) {
      const hasDataChannel = robot.connection.state === 'connected'
        && (robot.connection.dataMode === 'virtual' || robot.connection.dataMode === 'live')
      if (!hasDataChannel) {
        clear(robot.id)
        continue
      }
      if (lastSampleSecond[robot.id] === sampleSecond) continue

      const buffer = ensure(robot.id)
      const appended = [
        appendLimited(buffer.battery, robot.battery),
        appendLimited(buffer.latency, robot.latencyMs),
        appendLimited(buffer.speed, robot.speed)
      ].some(Boolean)
      if (appended) lastSampleSecond[robot.id] = sampleSecond
    }
  }

  function get(id: string): TrendBuffer {
    return ensure(id)
  }

  return { buffers, recordSnapshot, clear, clearAll, get }
})
