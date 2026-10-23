import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { TelemetrySnapshot, TelemetryValue } from '@/entities/types'

export interface TelemetryDisplaySample {
  id: string
  deviceId: string
  sampledAt: string
  fields: Record<string, TelemetryValue>
  latencyMs: number | null
}

const MAX_SAMPLES_PER_DEVICE = 60
const SAMPLE_INTERVAL_MS = 1_000

export const useTelemetryPresentationStore = defineStore('telemetry-presentation', () => {
  const samplesByDeviceId = ref<Record<string, TelemetryDisplaySample[]>>({})
  const lastSampleAtByDeviceId = new Map<string, number>()

  const totalSamples = computed(() =>
    Object.values(samplesByDeviceId.value).reduce((total, samples) => total + samples.length, 0)
  )

  function record(
    deviceId: string,
    snapshot: TelemetrySnapshot | undefined,
    latencyMs: number | null,
    force = false
  ): void {
    if (!snapshot) return
    const timestamp = Date.parse(snapshot.updatedAt)
    const sampledAt = Number.isFinite(timestamp) ? timestamp : Date.now()
    const previous = lastSampleAtByDeviceId.get(deviceId) ?? 0
    if (!force && sampledAt - previous < SAMPLE_INTERVAL_MS) return
    lastSampleAtByDeviceId.set(deviceId, sampledAt)
    const next: TelemetryDisplaySample = {
      id: `${deviceId}:${snapshot.revision}:${sampledAt}`,
      deviceId,
      sampledAt: new Date(sampledAt).toISOString(),
      fields: { ...snapshot.fields },
      latencyMs
    }
    const current = samplesByDeviceId.value[deviceId] ?? []
    samplesByDeviceId.value[deviceId] = [...current, next].slice(-MAX_SAMPLES_PER_DEVICE)
  }

  function samplesFor(deviceId: string): TelemetryDisplaySample[] {
    return samplesByDeviceId.value[deviceId] ?? []
  }

  function clearRuntime(): void {
    samplesByDeviceId.value = {}
    lastSampleAtByDeviceId.clear()
  }

  return { samplesByDeviceId, totalSamples, record, samplesFor, clearRuntime }
})
