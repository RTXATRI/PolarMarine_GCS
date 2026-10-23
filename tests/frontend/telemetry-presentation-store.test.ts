import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { TelemetrySnapshot } from '@/entities/types'
import { useTelemetryPresentationStore } from '@/entities/telemetry/presentation-store'

function snapshot(second: number, revision = second): TelemetrySnapshot {
  const timestamp = new Date(Date.UTC(2026, 6, 24, 1, 0, second)).toISOString()
  return {
    deviceId: 'device-1',
    fields: {
      speed: {
        value: second,
        sourceLinkId: 'link-1',
        collectedAt: timestamp,
        receivedAt: timestamp,
        quality: 'valid',
        unit: 'm/s'
      }
    },
    revision,
    updatedAt: timestamp
  }
}

describe('telemetry presentation cache', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('samples at no more than 1 Hz and retains only the newest 60 values', () => {
    const presentation = useTelemetryPresentationStore()
    presentation.record('device-1', snapshot(0), 12)
    presentation.record(
      'device-1',
      { ...snapshot(0, 2), updatedAt: '2026-07-24T01:00:00.500Z' },
      13
    )
    expect(presentation.samplesFor('device-1')).toHaveLength(1)

    for (let second = 1; second <= 65; second += 1) {
      presentation.record('device-1', snapshot(second), second)
    }

    const samples = presentation.samplesFor('device-1')
    expect(samples).toHaveLength(60)
    expect(samples[0].fields.speed.value).toBe(6)
    expect(samples.at(-1)?.fields.speed.value).toBe(65)
    expect(presentation.totalSamples).toBe(60)
  })

  it('supports forced bootstrap samples and clears all runtime-only data', () => {
    const presentation = useTelemetryPresentationStore()
    presentation.record('device-1', undefined, null)
    presentation.record('device-1', snapshot(0), 22, true)
    presentation.record('device-1', snapshot(0, 2), 23, true)
    expect(presentation.samplesFor('device-1')).toHaveLength(2)

    presentation.clearRuntime()
    expect(presentation.samplesByDeviceId).toEqual({})
    expect(presentation.totalSamples).toBe(0)
  })
})
