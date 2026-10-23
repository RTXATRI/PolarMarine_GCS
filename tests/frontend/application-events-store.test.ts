import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useApplicationStore } from '@/app/store'
import type { Alarm, PersistedEvent } from '@/entities/types'
import { useEventsStore } from '@/entities/events/store'
import type { StreamEvent } from '@/shared/api/event-schema'

const timestamp = '2026-07-23T08:00:00+00:00'

const persisted = (id: string, cursor: number): PersistedEvent => ({
  eventId: id,
  eventCursor: cursor,
  aggregateType: 'device',
  aggregateId: 'device-1',
  aggregateRevision: cursor,
  occurredAt: timestamp,
  type: 'device.changed',
  payload: { cursor }
})

const alarm = (id: string, acknowledged: boolean, minute: number): Alarm => ({
  id,
  severity: 'warning',
  code: 'TEST',
  message: id,
  deviceId: null,
  acknowledged,
  acknowledgedAt: acknowledged ? timestamp : null,
  createdAt: `2026-07-23T08:${String(minute).padStart(2, '0')}:00+00:00`,
  revision: 1
})

const streamEvent = (overrides: Partial<StreamEvent> = {}): StreamEvent => ({
  schemaVersion: '1.0',
  eventId: 'stream-1',
  serverInstanceId: 'server-1',
  connectionSequence: 1,
  eventCursor: 3,
  aggregateType: 'device',
  aggregateId: 'device-1',
  aggregateRevision: 3,
  occurredAt: timestamp,
  type: 'device.changed',
  payload: { source: 'test' },
  ...overrides
})

describe('application and event stores', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('keeps stream errors as local UI state only', () => {
    const application = useApplicationStore()
    application.setStreamState('connecting', 'waiting')
    expect(application.streamState).toBe('connecting')
    expect(application.lastError).toBe('waiting')
    application.setStreamState('connected')
    expect(application.lastError).toBeNull()
  })

  it('normalizes history, alarm state and bounded debug events', () => {
    const events = useEventsStore()
    events.replaceEvents([persisted('old', 1), persisted('new', 2)])
    expect(events.events.map((item) => item.eventId)).toEqual(['new', 'old'])

    events.replaceAlarms([alarm('ack', true, 1), alarm('open', false, 2)])
    expect(events.alarms.map((item) => item.id)).toEqual(['open', 'ack'])
    expect(events.activeAlarms.map((item) => item.id)).toEqual(['open'])
    events.upsertAlarm(alarm('open', true, 3))
    expect(events.activeAlarms).toEqual([])

    events.recordStreamEvent(streamEvent())
    events.recordStreamEvent(streamEvent({ payload: { source: 'updated' } }))
    expect(events.events[0].payload).toEqual({ source: 'updated' })
    events.recordStreamEvent(
      streamEvent({ eventId: 'debug-1', eventCursor: null, type: 'debug.ros_message' })
    )
    expect(events.rosDebugMessages).toHaveLength(1)
  })
})
