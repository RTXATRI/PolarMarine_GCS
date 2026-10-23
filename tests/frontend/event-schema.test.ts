import { describe, expect, it } from 'vitest'
import { streamEventSchema } from '@/shared/api/event-schema'

const baseEvent = {
  schemaVersion: '1.0',
  eventId: 'event-1',
  serverInstanceId: 'server-1',
  connectionSequence: 1,
  eventCursor: 1,
  aggregateType: 'command',
  aggregateId: 'command-1',
  aggregateRevision: 1,
  occurredAt: '2026-07-23T08:00:00+00:00'
}

describe('runtime event validation', () => {
  it('rejects an invalid known payload before it reaches a store', () => {
    const result = streamEventSchema.safeParse({
      ...baseEvent,
      type: 'command.changed',
      payload: { id: 'command-1' }
    })
    expect(result.success).toBe(false)
  })

  it('accepts forward-compatible unknown domain events', () => {
    const result = streamEventSchema.safeParse({
      ...baseEvent,
      type: 'future.aggregate.changed',
      payload: { extensionField: true }
    })
    expect(result.success).toBe(true)
  })
})
