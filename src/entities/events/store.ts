import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Alarm, PersistedEvent } from '@/entities/types'
import type { StreamEvent } from '@/shared/api/event-schema'

export const useEventsStore = defineStore('events', () => {
  const events = ref<PersistedEvent[]>([])
  const alarmsById = ref<Record<string, Alarm>>({})
  const rosDebugMessages = ref<StreamEvent[]>([])

  const alarms = computed(() =>
    Object.values(alarmsById.value).sort(
      (a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)
    )
  )
  const activeAlarms = computed(() => alarms.value.filter((item) => !item.acknowledged))

  function replaceEvents(next: PersistedEvent[]) {
    events.value = [...next].sort((a, b) => b.eventCursor - a.eventCursor).slice(0, 500)
  }

  function replaceAlarms(next: Alarm[]) {
    alarmsById.value = Object.fromEntries(next.map((item) => [item.id, item]))
  }

  function upsertAlarm(alarm: Alarm) {
    alarmsById.value[alarm.id] = alarm
  }

  function recordStreamEvent(event: StreamEvent) {
    if (event.type.startsWith('debug.ros')) {
      rosDebugMessages.value.unshift(event)
      rosDebugMessages.value = rosDebugMessages.value.slice(0, 500)
    }
    if (event.eventCursor == null) return
    const persisted: PersistedEvent = {
      eventId: event.eventId,
      eventCursor: event.eventCursor,
      aggregateType: event.aggregateType,
      aggregateId: event.aggregateId,
      aggregateRevision: event.aggregateRevision,
      occurredAt: event.occurredAt,
      type: event.type,
      payload: event.payload
    }
    const index = events.value.findIndex((item) => item.eventId === persisted.eventId)
    if (index >= 0) events.value[index] = persisted
    else events.value.unshift(persisted)
    events.value = events.value.slice(0, 500)
  }

  return {
    events,
    alarmsById,
    rosDebugMessages,
    alarms,
    activeAlarms,
    replaceEvents,
    replaceAlarms,
    upsertAlarm,
    recordStreamEvent
  }
})
