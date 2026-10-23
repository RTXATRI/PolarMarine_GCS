import { beforeEach, describe, expect, it, vi } from 'vitest'
import {
  isQuickMissionForDevice,
  quickMissionDescription,
  readQuickMissionId,
  writeQuickMissionId
} from '@/features/map/quick-mission-link'

describe('map quick mission local id mapping', () => {
  beforeEach(() => window.localStorage.clear())

  it('persists only the backend MissionPlan id mapping and can remove it', () => {
    writeQuickMissionId('device-1', 'mission-plan-1')
    expect(readQuickMissionId('device-1')).toBe('mission-plan-1')
    expect(readQuickMissionId('device-2')).toBeNull()

    writeQuickMissionId('device-1', null)
    expect(readQuickMissionId('device-1')).toBeNull()
  })

  it('ignores malformed storage and marks plans with a stable device marker', () => {
    window.localStorage.setItem('polarmarine-gcs-map-quick-missions-v1', '{invalid')
    expect(readQuickMissionId('device-1')).toBeNull()
    const description = quickMissionDescription('device-1')
    expect(isQuickMissionForDevice(description, 'device-1')).toBe(true)
    expect(isQuickMissionForDevice(description, 'device-2')).toBe(false)
  })

  it('keeps backend persistence authoritative if local storage is unavailable', () => {
    const failure = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('quota')
    })
    expect(() => writeQuickMissionId('device-1', 'mission-plan-1')).not.toThrow()
    failure.mockRestore()
  })
})
