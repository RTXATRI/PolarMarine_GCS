import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type {
  Bootstrap,
  Command,
  LinkProfile,
  LinkSessionState,
  MissionRun,
  TelemetrySnapshot
} from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import type { StreamEvent } from '@/shared/api/event-schema'

const timestamp = '2026-07-23T08:00:00+00:00'

function bootstrap(): Bootstrap {
  return {
    serverInstanceId: 'server-1',
    eventCursor: 0,
    templates: [
      {
        id: 'template-1',
        displayName: 'Template',
        category: 'generic',
        description: '',
        capabilities: [],
        parameters: [],
        mediaChannels: [],
        revision: 1,
        createdAt: timestamp,
        updatedAt: timestamp
      }
    ],
    devices: [
      {
        id: 'device-1',
        templateId: 'template-1',
        displayName: 'Device',
        enabled: true,
        description: '',
        tags: [],
        revision: 1,
        createdAt: timestamp,
        updatedAt: timestamp
      }
    ],
    links: [],
    linkSessions: [],
    operationalStates: [
      {
        deviceId: 'device-1',
        status: 'offline',
        activeLinkId: null,
        healthyLinkIds: [],
        lastFailoverAt: null,
        revision: 0
      }
    ],
    telemetrySnapshots: [],
    activeAlarms: [],
    recentCommands: [],
    activeMissionRuns: [],
    settings: {
      baiduMapAk: null,
      offlineMapStyleUrl: null,
      simulatorLabel: '仿真数据',
      maxConfiguredDevices: 50,
      maxOnlineDevices: 20
    }
  }
}

function sessionEvent(linkId: string, state: LinkSessionState, sequence: number): StreamEvent {
  return {
    schemaVersion: '1.0',
    eventId: 'event-' + sequence,
    serverInstanceId: 'server-1',
    connectionSequence: sequence,
    eventCursor: sequence,
    aggregateType: 'link_session',
    aggregateId: linkId,
    aggregateRevision: sequence,
    occurredAt: timestamp,
    type: 'link_session.changed',
    payload: {
      linkId,
      deviceId: 'device-1',
      driver: 'ros1',
      state,
      capabilities: [],
      startedAt: state === 'healthy' ? timestamp : null,
      healthySince: state === 'healthy' ? timestamp : null,
      lastHeartbeatAt: state === 'healthy' ? timestamp : null,
      latencyMs: null,
      packetLossPercent: null,
      debugAvailable: state === 'healthy',
      errorCode: null,
      errorMessage: null,
      revision: sequence
    }
  }
}

function event(
  type: string,
  payload: Record<string, unknown>,
  sequence: number,
  aggregateId = 'device-1'
): StreamEvent {
  return {
    schemaVersion: '1.0',
    eventId: `event-${type}-${sequence}`,
    serverInstanceId: 'server-1',
    connectionSequence: sequence,
    eventCursor: sequence,
    aggregateType: type.split('.')[0],
    aggregateId,
    aggregateRevision: sequence,
    occurredAt: timestamp,
    type,
    payload
  }
}

const command = (id: string): Command => ({
  id,
  deviceId: 'device-1',
  commandType: 'manual_control',
  payload: {},
  status: 'accepted',
  progress: null,
  result: {},
  routedLinkIds: ['primary'],
  linkAcknowledgements: { primary: 'accepted' },
  idempotencyKey: null,
  reasonCode: null,
  reasonMessage: null,
  requiresStateConfirmation: true,
  createdAt: timestamp,
  updatedAt: timestamp,
  expiresAt: null,
  revision: 1
})

const missionRun = (id: string): MissionRun => ({
  id,
  missionPlanId: 'plan-1',
  missionPlanVersion: 1,
  status: 'running',
  stepStates: { step: 'running' },
  planSteps: [],
  startedAt: timestamp,
  endedAt: null,
  revision: 1,
  createdAt: timestamp
})

const link = (id: string, priority: number): LinkProfile => ({
  id,
  deviceId: 'device-1',
  displayName: id,
  driver: 'ros1',
  role: priority === 1 ? 'primary' : 'auxiliary',
  priority,
  config: {},
  enabled: true,
  revision: 1,
  createdAt: timestamp,
  updatedAt: timestamp
})

describe('fleet normalized state', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('does not mark a healthy device degraded because another link is stopped', () => {
    const fleet = useFleetStore()
    fleet.applyBootstrap(bootstrap())
    fleet.applyStreamEvent(sessionEvent('primary', 'healthy', 1))
    fleet.applyStreamEvent(sessionEvent('auxiliary', 'stopped', 2))
    expect(fleet.operationsByDeviceId['device-1'].status).toBe('online')
  })

  it('clears runtime sessions and telemetry when the backend disconnects', () => {
    const fleet = useFleetStore()
    fleet.applyBootstrap(bootstrap())
    fleet.applyStreamEvent(sessionEvent('primary', 'healthy', 1))
    fleet.setBackendDisconnected('lost')
    expect(fleet.backendConnected).toBe(false)
    expect(fleet.sessionsByLinkId).toEqual({})
    expect(fleet.operationsByDeviceId['device-1'].status).toBe('offline')
  })

  it('applies every normalized runtime event without inventing device state', () => {
    const fleet = useFleetStore()
    const initial = bootstrap()
    initial.links = [link('auxiliary', 20), link('primary', 1)]
    initial.activeMissionRuns = [missionRun('run-1')]
    fleet.applyBootstrap(initial)

    expect(fleet.devices).toHaveLength(1)
    expect(fleet.templates).toHaveLength(1)
    expect(fleet.selectedDevice?.id).toBe('device-1')
    expect(fleet.selectedTemplate?.id).toBe('template-1')
    expect(fleet.selectedLinks.map((item) => item.id)).toEqual(['primary', 'auxiliary'])
    expect(fleet.selectedTelemetry).toBeNull()
    expect(fleet.onlineCount).toBe(0)
    fleet.selectDevice('missing')
    expect(fleet.selectedDeviceId).toBe('device-1')

    fleet.applyStreamEvent(sessionEvent('primary', 'healthy', 1))
    expect(fleet.selectedOnline).toBe(true)
    expect(fleet.onlineCount).toBe(1)
    fleet.applyStreamEvent(sessionEvent('auxiliary', 'healthy', 2))
    fleet.applyStreamEvent(sessionEvent('primary', 'stopped', 3))
    expect(fleet.selectedLinks.map((item) => item.id)).toEqual(['auxiliary', 'primary'])
    fleet.applyStreamEvent(sessionEvent('primary', 'healthy', 4))
    expect(fleet.selectedLinks.map((item) => item.id)).toEqual(['primary', 'auxiliary'])
    fleet.applyStreamEvent(
      event(
        'device.route_changed',
        {
          deviceId: 'device-1',
          previousLinkId: null,
          activeLinkId: 'primary',
          occurredAt: timestamp
        },
        2
      )
    )
    expect(fleet.selectedOperationalState?.activeLinkId).toBe('primary')

    const telemetryValue = {
      value: 80,
      sourceLinkId: 'primary',
      collectedAt: timestamp,
      receivedAt: timestamp,
      quality: 'valid',
      unit: '%'
    }
    fleet.applyStreamEvent(
      event(
        'telemetry.updated',
        { deviceId: 'device-1', fields: { battery: telemetryValue }, updatedAt: timestamp },
        3
      )
    )
    fleet.applyStreamEvent(
      event(
        'telemetry.quality_changed',
        {
          deviceId: 'device-1',
          fields: { speed: { ...telemetryValue, value: 1, unit: 'm/s' } },
          updatedAt: timestamp
        },
        4
      )
    )
    expect(Object.keys(fleet.selectedTelemetry?.fields ?? {})).toEqual(['battery', 'speed'])

    fleet.applyStreamEvent(event('command.changed', command('command-1'), 5))
    expect(fleet.commands[0].id).toBe('command-1')
    expect(
      fleet.applyStreamEvent(
        event(
          'mission_run.changed',
          {
            id: 'run-1',
            missionPlanId: 'plan-1',
            status: 'paused',
            stepStates: { step: 'paused' },
            reason: null
          },
          6,
          'run-1'
        )
      )
    ).toBe(false)
    expect(fleet.missionRunsById['run-1'].status).toBe('paused')
    expect(
      fleet.applyStreamEvent(
        event(
          'mission_run.changed',
          {
            id: 'missing-run',
            missionPlanId: 'plan-1',
            status: 'running',
            stepStates: {},
            reason: null
          },
          7,
          'missing-run'
        )
      )
    ).toBe(true)
    expect(fleet.applyStreamEvent(event('device.changed', {}, 8))).toBe(true)
    expect(fleet.applyStreamEvent(event('unrelated.changed', {}, 9))).toBe(false)

    fleet.upsertLink(link('temporary', 30))
    expect(fleet.linksById.temporary).toBeDefined()
    fleet.removeLink('temporary')
    expect(fleet.linksById.temporary).toBeUndefined()
    fleet.upsertCommand(command('command-2'))
    expect(fleet.commandsById['command-2']).toBeDefined()
  })

  it('covers empty, degraded and already-selected bootstrap branches', () => {
    const emptyFleet = useFleetStore()
    expect(emptyFleet.onlineCount).toBe(0)
    expect(emptyFleet.selectedDevice).toBeNull()
    expect(emptyFleet.selectedTemplate).toBeNull()
    const empty = bootstrap()
    empty.devices = []
    empty.operationalStates = []
    emptyFleet.applyBootstrap(empty)
    expect(emptyFleet.selectedDeviceId).toBe('')

    setActivePinia(createPinia())
    const fleet = useFleetStore()
    const initial = bootstrap()
    const telemetry: TelemetrySnapshot = {
      deviceId: 'device-1',
      fields: {},
      revision: 1,
      updatedAt: timestamp
    }
    initial.telemetrySnapshots = [telemetry]
    initial.recentCommands = [
      command('older'),
      { ...command('newer'), createdAt: '2026-07-23T09:00:00+00:00' }
    ]
    fleet.selectedDeviceId = 'device-1'
    fleet.applyBootstrap(initial)
    expect(fleet.selectedDeviceId).toBe('device-1')
    expect(fleet.selectedTelemetry).toEqual(telemetry)
    expect(fleet.commands.map((item) => item.id)).toEqual(['newer', 'older'])

    fleet.upsertSession({
      ...sessionEvent('degraded', 'degraded', 10).payload,
      linkId: 'degraded',
      deviceId: 'device-1',
      driver: 'ros1',
      state: 'degraded',
      capabilities: [],
      debugAvailable: false,
      revision: 10
    })
    expect(fleet.selectedOperationalState?.status).toBe('degraded')
    expect(fleet.selectedOnline).toBe(true)
    fleet.upsertSession({
      linkId: 'recovering',
      deviceId: 'device-1',
      driver: 'ros1',
      state: 'recovering',
      capabilities: [],
      debugAvailable: false,
      revision: 11
    })
    expect(fleet.selectedOperationalState?.status).toBe('degraded')

    const missingRoute = event(
      'device.route_changed',
      {
        deviceId: 'missing',
        previousLinkId: null,
        activeLinkId: null,
        occurredAt: timestamp
      },
      12
    )
    expect(fleet.applyStreamEvent(missingRoute)).toBe(false)
    expect(
      fleet.applyStreamEvent({
        ...event('device_template.changed', {}, 13),
        eventCursor: null
      })
    ).toBe(true)
    for (const type of [
      'link_profile.changed',
      'alarm.changed',
      'parameters.changed',
      'mission_plan.changed'
    ]) {
      expect(fleet.applyStreamEvent(event(type, {}, 14))).toBe(true)
    }

    fleet.selectDevice('device-1')
    fleet.setBackendDisconnected()
    expect(fleet.backendError).toBeNull()
    expect(fleet.selectedOnline).toBe(false)
  })
})
