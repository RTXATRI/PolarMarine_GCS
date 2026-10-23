import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { MissionPlan, MissionPlanWrite, MissionRun } from '@/entities/types'
import { api } from '@/shared/api/client'
import { missionRunPayloadSchema, type StreamEvent } from '@/shared/api/event-schema'

export const useMissionStore = defineStore('missions', () => {
  const plansById = ref<Record<string, MissionPlan>>({})
  const runsById = ref<Record<string, MissionRun>>({})
  const selectedPlanId = ref<string | null>(null)
  const loading = ref(false)

  const plans = computed(() =>
    Object.values(plansById.value).sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt))
  )
  const runs = computed(() =>
    Object.values(runsById.value).sort((a, b) => Date.parse(b.createdAt) - Date.parse(a.createdAt))
  )
  const selectedPlan = computed(() =>
    selectedPlanId.value ? (plansById.value[selectedPlanId.value] ?? null) : null
  )

  async function load() {
    loading.value = true
    try {
      const [planList, runList] = await Promise.all([api.listMissions(), api.listMissionRuns()])
      plansById.value = Object.fromEntries(planList.map((item) => [item.id, item]))
      runsById.value = Object.fromEntries(runList.map((item) => [item.id, item]))
      if (selectedPlanId.value && !plansById.value[selectedPlanId.value])
        selectedPlanId.value = null
    } finally {
      loading.value = false
    }
  }

  async function create(body: MissionPlanWrite): Promise<MissionPlan> {
    const plan = await api.createMission(body)
    plansById.value[plan.id] = plan
    selectedPlanId.value = plan.id
    return plan
  }

  async function update(id: string, body: MissionPlanWrite): Promise<MissionPlan> {
    const plan = await api.updateMission(id, body)
    plansById.value[id] = plan
    return plan
  }

  async function remove(id: string): Promise<void> {
    await api.deleteMission(id)
    delete plansById.value[id]
    if (selectedPlanId.value === id) selectedPlanId.value = null
  }

  async function start(id: string): Promise<MissionRun> {
    const run = await api.startMission(id)
    runsById.value[run.id] = run
    return run
  }

  async function control(runId: string, action: 'pause' | 'resume' | 'cancel') {
    return api.controlMission(runId, action)
  }

  function applyStreamEvent(event: StreamEvent): void {
    if (event.type !== 'mission_run.changed') return
    const payload = missionRunPayloadSchema.parse(event.payload)
    const current = runsById.value[event.aggregateId]
    if (!current) return
    runsById.value[event.aggregateId] = {
      ...current,
      status: payload.status,
      stepStates: payload.stepStates,
      revision: event.aggregateRevision
    }
  }

  return {
    plansById,
    runsById,
    selectedPlanId,
    loading,
    plans,
    runs,
    selectedPlan,
    load,
    create,
    update,
    remove,
    start,
    control,
    applyStreamEvent
  }
})
