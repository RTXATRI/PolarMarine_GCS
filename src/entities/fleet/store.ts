import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type {
  Bootstrap,
  Command,
  Device,
  DeviceTemplate,
  LinkProfile,
  LinkSession,
  LinkSessionState,
  MissionRun,
  OperationalState,
  TelemetrySnapshot
} from '@/entities/types'
import {
  commandPayloadSchema,
  linkSessionPayloadSchema,
  missionRunPayloadSchema,
  routeChangedPayloadSchema,
  telemetryPayloadSchema,
  type StreamEvent
} from '@/shared/api/event-schema'

type EntityMap<T> = Record<string, T>

const indexById = <T extends { id: string }>(items: T[]): EntityMap<T> =>
  Object.fromEntries(items.map((item) => [item.id, item]))

const linkStateRank: Record<LinkSessionState, number> = {
  healthy: 0,
  degraded: 1,
  handshaking: 2,
  recovering: 3,
  starting: 4,
  failed: 5,
  stopped: 6
}

export const useFleetStore = defineStore('fleet', () => {
  const templatesById = ref<EntityMap<DeviceTemplate>>({})
  const devicesById = ref<EntityMap<Device>>({})
  const linksById = ref<EntityMap<LinkProfile>>({})
  const sessionsByLinkId = ref<EntityMap<LinkSession>>({})
  const operationsByDeviceId = ref<EntityMap<OperationalState>>({})
  const telemetryByDeviceId = ref<EntityMap<TelemetrySnapshot>>({})
  const commandsById = ref<EntityMap<Command>>({})
  const missionRunsById = ref<EntityMap<MissionRun>>({})
  const selectedDeviceId = ref('')
  const backendConnected = ref(false)
  const backendError = ref<string | null>(null)
  const serverInstanceId = ref<string | null>(null)
  const eventCursor = ref(0)

  const devices = computed(() => Object.values(devicesById.value))
  const templates = computed(() => Object.values(templatesById.value))
  const links = computed(() => Object.values(linksById.value))
  const commands = computed(() =>
    Object.values(commandsById.value).sort(
      (a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt)
    )
  )
  const selectedDevice = computed(() => devicesById.value[selectedDeviceId.value] ?? null)
  const selectedTemplate = computed(() => {
    const device = selectedDevice.value
    return device ? (templatesById.value[device.templateId] ?? null) : null
  })
  const selectedOperationalState = computed(
    () => operationsByDeviceId.value[selectedDeviceId.value] ?? null
  )
  const selectedTelemetry = computed(
    () => telemetryByDeviceId.value[selectedDeviceId.value] ?? null
  )
  const selectedLinks = computed(() =>
    links.value
      .filter((link) => link.deviceId === selectedDeviceId.value)
      .sort((a, b) => {
        const stateA = sessionsByLinkId.value[a.id]?.state ?? 'stopped'
        const stateB = sessionsByLinkId.value[b.id]?.state ?? 'stopped'
        return (
          linkStateRank[stateA] - linkStateRank[stateB] ||
          a.priority - b.priority ||
          a.displayName.localeCompare(b.displayName)
        )
      })
  )
  const onlineCount = computed(() =>
    backendConnected.value
      ? Object.values(operationsByDeviceId.value).filter((item) => item.status !== 'offline').length
      : 0
  )
  const selectedOnline = computed(
    () =>
      backendConnected.value &&
      (selectedOperationalState.value?.status === 'online' ||
        selectedOperationalState.value?.status === 'degraded')
  )

  function applyBootstrap(payload: Bootstrap) {
    templatesById.value = indexById(payload.templates)
    devicesById.value = indexById(payload.devices)
    linksById.value = indexById(payload.links)
    sessionsByLinkId.value = Object.fromEntries(
      payload.linkSessions.map((item) => [item.linkId, item])
    )
    operationsByDeviceId.value = Object.fromEntries(
      payload.operationalStates.map((item) => [item.deviceId, item])
    )
    telemetryByDeviceId.value = Object.fromEntries(
      payload.telemetrySnapshots.map((item) => [item.deviceId, item])
    )
    commandsById.value = indexById(payload.recentCommands)
    missionRunsById.value = indexById(payload.activeMissionRuns)
    serverInstanceId.value = payload.serverInstanceId
    eventCursor.value = payload.eventCursor
    backendConnected.value = true
    backendError.value = null
    if (!devicesById.value[selectedDeviceId.value])
      selectedDeviceId.value = payload.devices[0]?.id ?? ''
  }

  function applyStreamEvent(event: StreamEvent): boolean {
    if (event.eventCursor != null)
      eventCursor.value = Math.max(eventCursor.value, event.eventCursor)
    if (event.type === 'link_session.changed') {
      const session = linkSessionPayloadSchema.parse(event.payload) as LinkSession
      sessionsByLinkId.value[session.linkId] = session
      rebuildOperational(session.deviceId)
      return false
    }
    if (event.type === 'device.route_changed') {
      const payload = routeChangedPayloadSchema.parse(event.payload)
      const deviceId = payload.deviceId
      const current = operationsByDeviceId.value[deviceId]
      if (current) {
        operationsByDeviceId.value[deviceId] = {
          ...current,
          activeLinkId: payload.activeLinkId,
          lastFailoverAt: payload.occurredAt,
          revision: event.aggregateRevision
        }
      }
      return false
    }
    if (event.type === 'telemetry.updated' || event.type === 'telemetry.quality_changed') {
      const payload = telemetryPayloadSchema.parse(event.payload)
      const deviceId = payload.deviceId
      const fields = payload.fields as TelemetrySnapshot['fields']
      const current = telemetryByDeviceId.value[deviceId]
      telemetryByDeviceId.value[deviceId] = {
        deviceId,
        fields: { ...current?.fields, ...fields },
        revision: event.aggregateRevision,
        updatedAt: payload.updatedAt
      }
      return false
    }
    if (event.type === 'command.changed') {
      const command = commandPayloadSchema.parse(event.payload) as Command
      commandsById.value[command.id] = command
      return false
    }
    if (event.type === 'mission_run.changed') {
      const payload = missionRunPayloadSchema.parse(event.payload)
      const current = missionRunsById.value[event.aggregateId]
      if (current) {
        missionRunsById.value[event.aggregateId] = {
          ...current,
          status: payload.status,
          stepStates: payload.stepStates,
          revision: event.aggregateRevision
        }
      }
      return current == null
    }
    return (
      event.type.startsWith('device.') ||
      event.type.startsWith('device_template.') ||
      event.type.startsWith('link_profile.') ||
      event.type.startsWith('alarm.') ||
      event.type.startsWith('parameters.') ||
      event.type.startsWith('mission_plan.')
    )
  }

  function rebuildOperational(deviceId: string) {
    const sessions = Object.values(sessionsByLinkId.value).filter(
      (item) => item.deviceId === deviceId
    )
    const healthy = sessions.filter((item) => item.state === 'healthy' || item.state === 'degraded')
    const current = operationsByDeviceId.value[deviceId]
    const activeLinkId = healthy.some((item) => item.linkId === current?.activeLinkId)
      ? (current?.activeLinkId ?? null)
      : null
    operationsByDeviceId.value[deviceId] = {
      deviceId,
      status:
        healthy.length === 0
          ? 'offline'
          : sessions.some((item) => ['degraded', 'recovering', 'failed'].includes(item.state))
            ? 'degraded'
            : 'online',
      activeLinkId,
      healthyLinkIds: healthy.map((item) => item.linkId),
      lastFailoverAt: current?.lastFailoverAt ?? null,
      revision: Math.max(current?.revision ?? 0, ...sessions.map((item) => item.revision))
    }
  }

  function setBackendDisconnected(message?: string) {
    backendConnected.value = false
    backendError.value = message ?? null
    sessionsByLinkId.value = {}
    telemetryByDeviceId.value = {}
    operationsByDeviceId.value = Object.fromEntries(
      devices.value.map((device) => [
        device.id,
        {
          deviceId: device.id,
          status: 'offline',
          activeLinkId: null,
          healthyLinkIds: [],
          lastFailoverAt: null,
          revision: 0
        }
      ])
    )
  }

  function selectDevice(deviceId: string) {
    if (devicesById.value[deviceId]) selectedDeviceId.value = deviceId
  }

  function upsertLink(link: LinkProfile) {
    linksById.value[link.id] = link
  }

  function removeLink(linkId: string) {
    delete linksById.value[linkId]
    delete sessionsByLinkId.value[linkId]
  }

  function upsertSession(session: LinkSession) {
    sessionsByLinkId.value[session.linkId] = session
    rebuildOperational(session.deviceId)
  }

  function upsertCommand(command: Command) {
    commandsById.value[command.id] = command
  }

  return {
    templatesById,
    devicesById,
    linksById,
    sessionsByLinkId,
    operationsByDeviceId,
    telemetryByDeviceId,
    commandsById,
    missionRunsById,
    selectedDeviceId,
    backendConnected,
    backendError,
    serverInstanceId,
    eventCursor,
    devices,
    templates,
    links,
    commands,
    selectedDevice,
    selectedTemplate,
    selectedOperationalState,
    selectedTelemetry,
    selectedLinks,
    selectedOnline,
    onlineCount,
    applyBootstrap,
    applyStreamEvent,
    setBackendDisconnected,
    selectDevice,
    upsertLink,
    removeLink,
    upsertSession,
    upsertCommand
  }
})
