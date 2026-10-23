import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { MissionPlan, MissionPlanWrite, MissionRun } from '@/entities/types'
import { useMissionStore } from '@/entities/mission/store'
import { api } from '@/shared/api/client'
import type { StreamEvent } from '@/shared/api/event-schema'

const timestamp = '2026-07-23T08:00:00+00:00'
const body: MissionPlanWrite = { name: '巡检', description: '', steps: [] }

const plan = (id: string, version = 1): MissionPlan => ({
  ...body,
  id,
  version,
  status: 'valid',
  revision: version,
  createdAt: timestamp,
  updatedAt: `2026-07-23T08:0${version}:00+00:00`
})

const run = (id: string): MissionRun => ({
  id,
  missionPlanId: 'plan-1',
  missionPlanVersion: 1,
  status: 'running',
  stepStates: {},
  planSteps: [],
  startedAt: timestamp,
  endedAt: null,
  revision: 1,
  createdAt: timestamp
})

describe('mission store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.restoreAllMocks()
  })

  it('loads and mutates only server-returned plans and runs', async () => {
    vi.spyOn(api, 'listMissions').mockResolvedValue([plan('plan-1'), plan('plan-2', 2)])
    vi.spyOn(api, 'listMissionRuns').mockResolvedValue([run('run-1')])
    const missions = useMissionStore()
    missions.selectedPlanId = 'missing'
    await missions.load()
    expect(missions.loading).toBe(false)
    expect(missions.selectedPlanId).toBeNull()
    expect(missions.plans.map((item) => item.id)).toEqual(['plan-2', 'plan-1'])
    expect(missions.runs[0].id).toBe('run-1')

    vi.spyOn(api, 'createMission').mockResolvedValue(plan('plan-3'))
    expect((await missions.create(body)).id).toBe('plan-3')
    expect(missions.selectedPlan?.id).toBe('plan-3')

    vi.spyOn(api, 'updateMission').mockResolvedValue(plan('plan-3', 2))
    expect((await missions.update('plan-3', body)).version).toBe(2)

    vi.spyOn(api, 'startMission').mockResolvedValue(run('run-2'))
    expect((await missions.start('plan-3')).id).toBe('run-2')

    const control = vi
      .spyOn(api, 'controlMission')
      .mockResolvedValue({ missionRunId: 'run-2', commands: [] })
    await missions.control('run-2', 'pause')
    expect(control).toHaveBeenCalledWith('run-2', 'pause')

    vi.spyOn(api, 'deleteMission').mockResolvedValue(undefined)
    await missions.remove('plan-3')
    expect(missions.selectedPlanId).toBeNull()
    expect(missions.plansById['plan-3']).toBeUndefined()
  })

  it('preserves a valid selection and always clears the loading guard on failure', async () => {
    const missions = useMissionStore()
    expect(missions.selectedPlan).toBeNull()
    missions.plansById['plan-1'] = plan('plan-1')
    missions.selectedPlanId = 'plan-1'
    vi.spyOn(api, 'listMissions').mockResolvedValue([plan('plan-1')])
    vi.spyOn(api, 'listMissionRuns').mockResolvedValue([
      run('old-run'),
      { ...run('new-run'), createdAt: '2026-07-23T09:00:00+00:00' }
    ])
    await missions.load()
    expect(missions.selectedPlan?.id).toBe('plan-1')
    expect(missions.runs.map((item) => item.id)).toEqual(['new-run', 'old-run'])

    missions.plansById.other = plan('other')
    vi.spyOn(api, 'deleteMission').mockResolvedValue(undefined)
    await missions.remove('other')
    expect(missions.selectedPlanId).toBe('plan-1')

    vi.spyOn(api, 'listMissions').mockRejectedValueOnce(new Error('offline'))
    await expect(missions.load()).rejects.toThrow('offline')
    expect(missions.loading).toBe(false)
  })

  it('applies only device-reported MissionRun stream progress to known runs', () => {
    const missions = useMissionStore()
    missions.runsById['run-1'] = run('run-1')
    const event: StreamEvent = {
      schemaVersion: '1.0',
      eventId: 'mission-run-event',
      serverInstanceId: 'server-1',
      connectionSequence: 1,
      eventCursor: 1,
      aggregateType: 'mission_run',
      aggregateId: 'run-1',
      aggregateRevision: 2,
      occurredAt: timestamp,
      type: 'mission_run.changed',
      payload: {
        id: 'run-1',
        missionPlanId: 'plan-1',
        status: 'paused',
        stepStates: { route: 'paused' },
        reason: null
      }
    }
    missions.applyStreamEvent(event)
    expect(missions.runsById['run-1'].status).toBe('paused')
    expect(missions.runsById['run-1'].stepStates).toEqual({ route: 'paused' })
    expect(missions.runsById['run-1'].revision).toBe(2)

    missions.applyStreamEvent({ ...event, aggregateId: 'unknown-run' })
    expect(missions.runsById['unknown-run']).toBeUndefined()
    missions.applyStreamEvent({ ...event, type: 'debug.ros_response', payload: {} })
    expect(missions.runsById['run-1'].status).toBe('paused')
  })
})
