<template>
  <div class="mission-page">
    <aside class="task-types panel">
      <div class="panel-heading">
        <div>
          <h2>任务类型</h2>
          <span>{{ fleet.selectedDevice?.displayName ?? '未选择设备' }}</span>
        </div>
      </div>
      <div class="task-list">
        <button
          v-for="task in availableTasks"
          :key="task.id"
          class="task-type"
          :class="{ active: selectedTaskId === task.id }"
          type="button"
          @click="selectTask(task.id)"
        >
          <el-icon><component :is="task.icon" /></el-icon>
          <span>
            <b>{{ task.name }}</b>
            <small>{{ task.description }}</small>
          </span>
        </button>
        <div v-if="!availableTasks.length" class="empty">
          当前设备模板没有声明可创建的任务能力。
        </div>
      </div>
      <div class="task-tools">
        <el-button size="small" @click="advancedVisible = true">高级编排 / 历史 / 录制</el-button>
      </div>
    </aside>

    <section class="task-config panel">
      <div class="panel-heading">
        <div>
          <h2>任务配置</h2>
          <span>所有任务都会持久化为 MissionPlan</span>
        </div>
        <StatusBadge
          v-if="selectedTask"
          :label="selectedTask.capability"
          :tone="fleet.selectedOnline ? 'info' : 'warning'"
        />
      </div>
      <div v-if="selectedTask" class="config-body">
        <el-form label-position="top">
          <el-form-item label="任务名称">
            <el-input v-model="taskName" maxlength="128" />
          </el-form-item>

          <template v-if="selectedTask.kind === 'waypoint'">
            <div class="coordinate-heading">
              <b>WGS-84 目标点</b>
              <el-button size="small" :disabled="!currentCoordinate" @click="useCurrentCoordinate">
                使用当前位置
              </el-button>
            </div>
            <div class="coordinate-grid">
              <el-form-item label="纬度">
                <el-input-number
                  v-model="waypoint.latitude"
                  :min="-90"
                  :max="90"
                  :precision="7"
                  :controls="false"
                />
              </el-form-item>
              <el-form-item label="经度">
                <el-input-number
                  v-model="waypoint.longitude"
                  :min="-180"
                  :max="180"
                  :precision="7"
                  :controls="false"
                />
              </el-form-item>
              <el-form-item label="期望速度">
                <el-input-number v-model="waypoint.speed" :min="0" :step="0.1" :precision="2" />
                <span class="unit">m/s</span>
              </el-form-item>
            </div>
          </template>

          <template v-else-if="selectedTask.kind === 'route'">
            <div class="coordinate-heading">
              <div>
                <b>路线航点</b>
                <span>航点顺序将作为同一个 route 步骤提交。</span>
              </div>
              <el-button size="small" @click="addRoutePoint">添加航点</el-button>
            </div>
            <div class="route-points">
              <article v-for="(point, index) in routePoints" :key="point.id">
                <span class="index">{{ index + 1 }}</span>
                <el-input-number
                  v-model="point.latitude"
                  :min="-90"
                  :max="90"
                  :precision="7"
                  :controls="false"
                  placeholder="纬度"
                />
                <el-input-number
                  v-model="point.longitude"
                  :min="-180"
                  :max="180"
                  :precision="7"
                  :controls="false"
                  placeholder="经度"
                />
                <el-input-number
                  v-model="point.speed"
                  :min="0"
                  :step="0.1"
                  :precision="2"
                  placeholder="速度"
                />
                <el-button link type="danger" @click="routePoints.splice(index, 1)">删除</el-button>
              </article>
              <div v-if="!routePoints.length" class="route-empty">
                尚未添加航点；不会自动注入演示坐标。
              </div>
            </div>
            <div class="route-options">
              <span>默认巡航速度</span>
              <el-input-number v-model="routeCruiseSpeed" :min="0" :step="0.1" :precision="2" />
              <span>m/s</span>
              <el-checkbox v-model="routeLoop">循环路线</el-checkbox>
            </div>
          </template>

          <template v-else-if="selectedTask.kind === 'return_home'">
            <el-alert
              type="warning"
              :closable="false"
              show-icon
              title="执行前后端会检查健康链路、定位、电池与设备返回的 Home 点。"
            />
            <div class="preflight-list">
              <div>
                <span>健康控制链路</span><b>{{ fleet.selectedOnline ? '可用' : '不可用' }}</b>
              </div>
              <div>
                <span>当前位置</span><b>{{ currentCoordinate ? '有效' : '无效/过期' }}</b>
              </div>
              <div>
                <span>Home 点</span><b>{{ homeCoordinate ? '有效' : '无效/过期' }}</b>
              </div>
            </div>
          </template>

          <template v-else>
            <el-alert
              type="info"
              :closable="false"
              :title="`${selectedTask.name} 只有在设备声明 ${selectedTask.capability} 时才会出现。`"
            />
            <el-form-item label="动作参数 JSON">
              <el-input v-model="customPayloadJson" type="textarea" :rows="10" class="mono" />
            </el-form-item>
          </template>
        </el-form>
      </div>
      <div v-else class="empty">请选择一种设备支持的任务类型。</div>
      <div class="config-footer">
        <span>{{ configHint }}</span>
        <div>
          <el-button :disabled="!canCreate" :loading="savingPlan" @click="createQuickPlan(false)">
            保存计划
          </el-button>
          <el-button
            type="primary"
            :disabled="!canCreate || !fleet.selectedOnline"
            :loading="savingAndStarting"
            @click="createQuickPlan(true)"
          >
            保存并执行
          </el-button>
        </div>
      </div>
    </section>

    <aside class="execution-status panel">
      <div class="panel-heading">
        <div>
          <h2>执行状态</h2>
          <span>进度仅来自 MissionRun / Command 事件</span>
        </div>
        <el-button size="small" @click="refreshMissionData">刷新</el-button>
      </div>
      <div v-if="currentPlan" class="run-body">
        <section class="plan-summary">
          <div>
            <b>{{ currentPlan.name }}</b>
            <StatusBadge :label="`v${currentPlan.version}`" tone="info" />
          </div>
          <span class="mono">{{ currentPlan.id }}</span>
          <p>{{ currentPlan.description || '无说明' }}</p>
        </section>

        <section v-if="currentRun" class="run-summary">
          <div class="run-state">
            <b>任务运行</b>
            <StatusBadge
              :label="runStatusLabel(currentRun.status)"
              :tone="runTone(currentRun.status)"
            />
          </div>
          <span class="mono">{{ currentRun.id }}</span>
          <el-progress
            :percentage="runProgress"
            :status="currentRun.status === 'failed' ? 'exception' : undefined"
          />
          <div class="step-states">
            <div v-for="step in currentRun.planSteps" :key="step.id">
              <span>{{ step.id }}</span>
              <b>{{ currentRun.stepStates[step.id] ?? 'queued' }}</b>
            </div>
          </div>
          <div v-if="['running', 'paused'].includes(currentRun.status)" class="run-actions">
            <el-button
              v-if="currentRun.status === 'running'"
              size="small"
              @click="controlRun('pause')"
            >
              暂停
            </el-button>
            <el-button v-else size="small" @click="controlRun('resume')">恢复</el-button>
            <el-button size="small" type="danger" plain @click="controlRun('cancel')">
              取消
            </el-button>
          </div>
        </section>
        <section v-else class="no-run">
          <span>该计划尚无活动运行。</span>
          <el-button
            type="primary"
            size="small"
            :disabled="!fleet.selectedOnline"
            :loading="startingExisting"
            @click="startExistingPlan"
          >
            执行当前计划
          </el-button>
        </section>

        <section class="plan-steps">
          <h3>计划步骤</h3>
          <div v-for="(step, index) in currentPlan.steps" :key="step.id">
            <span>{{ index + 1 }}</span>
            <b>{{ stepTypeLabel(step.stepType) }}</b>
            <small>{{ fleet.devicesById[step.deviceId]?.displayName ?? step.deviceId }}</small>
          </div>
        </section>
      </div>
      <div v-else class="empty">保存快捷任务或从高级编排中选择一个计划。</div>
    </aside>

    <AdvancedMissionDrawer v-model="advancedVisible" />
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, onMounted, reactive, ref, watch } from 'vue'
import { Aim, Compass, Connection, Delete, Position, RefreshRight } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { MissionPlanWrite, MissionRun, MissionStep } from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import { useMissionStore } from '@/entities/mission/store'
import AdvancedMissionDrawer from '@/features/missions/AdvancedMissionDrawer.vue'
import { numericTelemetry } from '@/shared/lib/device-view'
import StatusBadge from '@/shared/ui/StatusBadge.vue'

type TaskKind = 'waypoint' | 'route' | 'return_home' | 'custom_action'

interface TaskOption {
  id: string
  name: string
  description: string
  kind: TaskKind
  capability: string
  icon: object
}

interface RoutePoint {
  id: string
  latitude?: number
  longitude?: number
  speed: number
}

const fleet = useFleetStore()
const missions = useMissionStore()
const advancedVisible = ref(false)
const selectedTaskId = ref('')
const taskName = ref('')
const waypoint = reactive<{ latitude?: number; longitude?: number; speed: number }>({
  speed: 0.3
})
const routePoints = ref<RoutePoint[]>([])
const routeCruiseSpeed = ref(0.3)
const routeLoop = ref(false)
const customPayloadJson = ref('{}')
const savingPlan = ref(false)
const savingAndStarting = ref(false)
const startingExisting = ref(false)
const currentPlanId = ref<string | null>(null)

const availableTasks = computed<TaskOption[]>(() => {
  const capabilities = fleet.selectedTemplate?.capabilities ?? []
  const tasks: TaskOption[] = []
  if (capabilities.includes('mission.waypoint'))
    tasks.push({
      id: 'waypoint',
      name: '目标点任务',
      description: '前往单个 WGS-84 目标点',
      kind: 'waypoint',
      capability: 'mission.waypoint',
      icon: markRaw(Aim)
    })
  if (capabilities.includes('mission.route'))
    tasks.push({
      id: 'route',
      name: '路线任务',
      description: '按顺序执行多个航点',
      kind: 'route',
      capability: 'mission.route',
      icon: markRaw(Position)
    })
  if (capabilities.includes('mission.return_home'))
    tasks.push({
      id: 'return_home',
      name: '返航',
      description: '使用设备已确认的 Home 点',
      kind: 'return_home',
      capability: 'mission.return_home',
      icon: markRaw(RefreshRight)
    })
  const customLabels: Record<string, [string, string, object]> = {
    'dock.charge': ['返航充电', '执行设备声明的停靠/充电流程', markRaw(Connection)],
    'payload.waste_collection': ['垃圾收集', '执行真实负载垃圾收集流程', markRaw(Delete)],
    'payload.electromagnetic_fix': ['电磁固定', '控制设备声明的电磁作业载荷', markRaw(Compass)]
  }
  for (const capability of capabilities) {
    const definition = customLabels[capability]
    if (!definition) continue
    tasks.push({
      id: capability,
      name: definition[0],
      description: definition[1],
      kind: 'custom_action',
      capability,
      icon: definition[2]
    })
  }
  return tasks
})
const selectedTask = computed(
  () => availableTasks.value.find((task) => task.id === selectedTaskId.value) ?? null
)
const currentPlan = computed(() => {
  const deviceId = fleet.selectedDeviceId
  const explicit = currentPlanId.value ? missions.plansById[currentPlanId.value] : undefined
  if (explicit?.steps.some((step) => step.deviceId === deviceId)) return explicit
  if (missions.selectedPlan?.steps.some((step) => step.deviceId === deviceId))
    return missions.selectedPlan
  const activeRun = missions.runs.find(
    (run) =>
      ['queued', 'running', 'paused'].includes(run.status) &&
      run.planSteps.some((step) => step.deviceId === deviceId)
  )
  return (
    (activeRun ? missions.plansById[activeRun.missionPlanId] : undefined) ??
    missions.plans.find((plan) => plan.steps.some((step) => step.deviceId === deviceId)) ??
    null
  )
})
const currentRun = computed<MissionRun | null>(() => {
  const planId = currentPlan.value?.id
  if (!planId) return null
  return (
    missions.runs.find(
      (run) => run.missionPlanId === planId && ['queued', 'running', 'paused'].includes(run.status)
    ) ??
    missions.runs.find((run) => run.missionPlanId === planId) ??
    null
  )
})
const currentCoordinate = computed(() => {
  const latitude = numericTelemetry(fleet.selectedTelemetry, 'position.latitude')
  const longitude = numericTelemetry(fleet.selectedTelemetry, 'position.longitude')
  return latitude == null || longitude == null ? null : { latitude, longitude }
})
const homeCoordinate = computed(() => {
  const latitude = numericTelemetry(fleet.selectedTelemetry, 'home.latitude')
  const longitude = numericTelemetry(fleet.selectedTelemetry, 'home.longitude')
  return latitude == null || longitude == null ? null : { latitude, longitude }
})
const canCreate = computed(() =>
  Boolean(fleet.selectedDevice && selectedTask.value && isConfigValid())
)
const configHint = computed(() => {
  if (!fleet.selectedDevice) return '请先选择设备'
  if (!selectedTask.value) return '当前模板没有可用任务类型'
  if (!isConfigValid()) return '请补全任务配置'
  return fleet.selectedOnline
    ? '可保存或执行；执行前仍会进行服务端预检'
    : '设备离线：可保存计划，但不能执行'
})
const runProgress = computed(() => {
  if (!currentRun.value?.planSteps.length) return 0
  const completed = currentRun.value.planSteps.filter((step) =>
    ['completed', 'succeeded'].includes(currentRun.value?.stepStates[step.id] ?? '')
  ).length
  return Math.round((completed / currentRun.value.planSteps.length) * 100)
})

onMounted(refreshMissionData)
watch(
  () => fleet.selectedDeviceId,
  () => {
    const first = availableTasks.value[0]
    selectTask(first?.id ?? '')
    selectRelevantPlan()
  },
  { immediate: true }
)
watch(
  () => missions.selectedPlanId,
  (planId) => {
    if (planId) currentPlanId.value = planId
  }
)

function selectTask(taskId: string): void {
  selectedTaskId.value = taskId
  const task = availableTasks.value.find((item) => item.id === taskId)
  taskName.value =
    task && fleet.selectedDevice ? `${fleet.selectedDevice.displayName} · ${task.name}` : ''
  customPayloadJson.value = '{}'
}

function useCurrentCoordinate(): void {
  if (!currentCoordinate.value) return
  waypoint.latitude = currentCoordinate.value.latitude
  waypoint.longitude = currentCoordinate.value.longitude
}

function addRoutePoint(): void {
  const current = currentCoordinate.value
  routePoints.value.push({
    id: crypto.randomUUID(),
    latitude: current?.latitude,
    longitude: current?.longitude,
    speed: routeCruiseSpeed.value
  })
}

async function createQuickPlan(startAfterSave: boolean): Promise<void> {
  if (!canCreate.value || !selectedTask.value || !fleet.selectedDevice) return
  const loading = startAfterSave ? savingAndStarting : savingPlan
  loading.value = true
  try {
    const plan = await missions.create(buildPlan())
    currentPlanId.value = plan.id
    missions.selectedPlanId = plan.id
    ElMessage.success('任务计划已持久化')
    if (startAfterSave) {
      const run = await missions.start(plan.id)
      ElMessage.info(`任务运行 ${run.id} 已创建，等待设备 ACK`)
    }
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '任务创建失败')
  } finally {
    loading.value = false
  }
}

function buildPlan(): MissionPlanWrite {
  const task = selectedTask.value
  const device = fleet.selectedDevice
  if (!task || !device) throw new Error('未选择任务或设备')
  const step: MissionStep = {
    id: `quick-${task.kind}`,
    stepType: task.kind,
    deviceId: device.id,
    dependsOn: [],
    timeoutSeconds: task.kind === 'return_home' ? 300 : 900,
    payload: taskPayload(task)
  }
  return {
    name: taskName.value.trim(),
    description: `快捷任务 · capability=${task.capability}`,
    steps: [step]
  }
}

function taskPayload(task: TaskOption): Record<string, unknown> {
  if (task.kind === 'waypoint')
    return {
      latitude: waypoint.latitude,
      longitude: waypoint.longitude,
      speed: waypoint.speed,
      coordinateReference: 'WGS-84'
    }
  if (task.kind === 'route')
    return {
      waypoints: routePoints.value.map((point) => ({
        latitude: point.latitude,
        longitude: point.longitude,
        speed: point.speed || routeCruiseSpeed.value
      })),
      cruiseSpeed: routeCruiseSpeed.value,
      loop: routeLoop.value,
      coordinateReference: 'WGS-84'
    }
  if (task.kind === 'return_home') return {}
  const parsed: unknown = JSON.parse(customPayloadJson.value)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
    throw new Error('动作参数必须是 JSON 对象')
  return {
    ...(parsed as Record<string, unknown>),
    capability: task.capability,
    action: task.id
  }
}

function isConfigValid(): boolean {
  if (!taskName.value.trim() || !selectedTask.value) return false
  if (selectedTask.value.kind === 'waypoint')
    return waypoint.latitude != null && waypoint.longitude != null
  if (selectedTask.value.kind === 'route')
    return (
      routePoints.value.length >= 2 &&
      routePoints.value.every((point) => point.latitude != null && point.longitude != null)
    )
  if (selectedTask.value.kind === 'custom_action') {
    try {
      const parsed: unknown = JSON.parse(customPayloadJson.value)
      return Boolean(parsed && typeof parsed === 'object' && !Array.isArray(parsed))
    } catch {
      return false
    }
  }
  return true
}

async function startExistingPlan(): Promise<void> {
  if (!currentPlan.value || !fleet.selectedOnline) return
  startingExisting.value = true
  try {
    const run = await missions.start(currentPlan.value.id)
    ElMessage.info(`任务运行 ${run.id} 已创建，等待设备 ACK`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '任务启动失败')
  } finally {
    startingExisting.value = false
  }
}

async function controlRun(action: 'pause' | 'resume' | 'cancel'): Promise<void> {
  if (!currentRun.value) return
  try {
    const receipt = await missions.control(currentRun.value.id, action)
    for (const command of receipt.commands) fleet.upsertCommand(command)
    ElMessage.info('任务控制请求已提交，等待设备确认')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '任务控制失败')
  }
}

async function refreshMissionData(): Promise<void> {
  try {
    await missions.load()
    selectRelevantPlan()
  } catch {
    ElMessage.error('任务数据读取失败')
  }
}

function selectRelevantPlan(): void {
  const deviceId = fleet.selectedDeviceId
  if (!deviceId) {
    currentPlanId.value = null
    return
  }
  const selected = missions.selectedPlan
  if (selected?.steps.some((step) => step.deviceId === deviceId)) {
    currentPlanId.value = selected.id
    return
  }
  const activeRun = missions.runs.find(
    (run) =>
      ['queued', 'running', 'paused'].includes(run.status) &&
      run.planSteps.some((step) => step.deviceId === deviceId)
  )
  const preferredPlan =
    (activeRun ? missions.plansById[activeRun.missionPlanId] : undefined) ??
    missions.plans.find((plan) => plan.steps.some((step) => step.deviceId === deviceId))
  currentPlanId.value = preferredPlan?.id ?? null
  if (preferredPlan) missions.selectedPlanId = preferredPlan.id
}

function runStatusLabel(status: MissionRun['status']): string {
  const labels: Record<MissionRun['status'], string> = {
    queued: '排队中',
    running: '执行中',
    paused: '已暂停',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return labels[status]
}

function runTone(
  status: MissionRun['status']
): 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'simulation' {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'paused') return 'warning'
  if (status === 'running' || status === 'queued') return 'info'
  return 'neutral'
}

function stepTypeLabel(stepType: string): string {
  return (
    {
      waypoint: '目标点',
      route: '路线',
      return_home: '返航',
      custom_action: '自定义动作'
    }[stepType] ?? stepType
  )
}
</script>

<style scoped>
.mission-page {
  display: grid;
  grid-template-columns: 220px minmax(430px, 1fr) 280px;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.task-types,
.task-config,
.execution-status {
  display: flex;
  min-height: 0;
  flex-direction: column;
  overflow: hidden;
}

.panel-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  flex: 0 0 54px;
  min-height: 54px;
  padding: 9px 12px;
  border-bottom: 1px solid var(--border);
}

.panel-heading h2,
.plan-steps h3 {
  margin: 0;
  color: var(--text-1);
  font-size: 13px;
}

.panel-heading span {
  display: block;
  margin-top: 3px;
  color: var(--text-3);
  font-size: 9.5px;
}

.task-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 6px;
  min-height: 0;
  padding: 10px;
  overflow-y: auto;
}

.task-type {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 10px;
  color: var(--text-1);
  text-align: left;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-panel-2);
  cursor: pointer;
}

.task-type:hover {
  border-color: var(--border-strong);
}

.task-type.active {
  border-color: var(--color-accent);
  background: rgb(59 130 246 / 10%);
}

.task-type .el-icon {
  flex: 0 0 auto;
  color: var(--color-accent);
  font-size: 20px;
}

.task-type > span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.task-type small {
  color: var(--text-3);
  font-size: 10.5px;
}

.task-tools {
  padding: 9px 10px;
  border-top: 1px solid var(--border);
}

.task-tools .el-button {
  width: 100%;
}

.config-body {
  flex: 1;
  min-height: 0;
  padding: 14px 16px;
  overflow-y: auto;
}

.coordinate-heading,
.route-options,
.config-footer,
.run-state,
.run-actions {
  display: flex;
  align-items: center;
}

.coordinate-heading {
  justify-content: space-between;
  gap: 10px;
  margin: 4px 0 10px;
}

.coordinate-heading div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.coordinate-heading span {
  color: var(--text-3);
  font-size: 10.5px;
}

.coordinate-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 0.8fr;
  gap: 12px;
}

.coordinate-grid :deep(.el-input-number) {
  width: 100%;
}

.unit {
  margin-left: 7px;
  color: var(--text-3);
}

.route-points {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.route-points article {
  display: grid;
  grid-template-columns: 30px minmax(120px, 1fr) minmax(120px, 1fr) 115px auto;
  align-items: center;
  gap: 7px;
  padding: 8px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.route-points :deep(.el-input-number) {
  width: 100%;
}

.index {
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  color: var(--color-accent);
  border-radius: 50%;
  background: rgb(59 130 246 / 12%);
}

.route-empty {
  padding: 24px;
  color: var(--text-3);
  border: 1px dashed var(--border);
  border-radius: var(--radius-sm);
  text-align: center;
}

.route-options {
  gap: 9px;
  margin-top: 12px;
  color: var(--text-3);
}

.preflight-list {
  display: grid;
  gap: 7px;
  margin-top: 12px;
}

.preflight-list div {
  display: flex;
  justify-content: space-between;
  padding: 8px 10px;
  border-bottom: 1px dashed var(--border);
}

.config-footer {
  justify-content: space-between;
  gap: 12px;
  flex: 0 0 52px;
  min-height: 52px;
  padding: 8px 12px;
  border-top: 1px solid var(--border);
}

.config-footer > span {
  color: var(--text-3);
  font-size: 10.5px;
}

.run-body {
  flex: 1;
  min-height: 0;
  padding: 10px;
  overflow-y: auto;
}

.plan-summary,
.run-summary,
.no-run,
.plan-steps {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-panel-2);
}

.plan-summary > div,
.run-state {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.plan-summary > span,
.run-summary > span {
  display: block;
  margin-top: 5px;
  overflow: hidden;
  color: var(--text-muted);
  font-size: 9px;
  text-overflow: ellipsis;
}

.plan-summary p {
  margin: 7px 0 0;
  color: var(--text-3);
  font-size: 10.5px;
  line-height: 1.45;
}

.run-summary,
.no-run,
.plan-steps {
  margin-top: 9px;
}

.run-summary :deep(.el-progress) {
  margin-top: 10px;
}

.step-states {
  display: grid;
  gap: 5px;
  margin-top: 9px;
}

.step-states div {
  display: flex;
  justify-content: space-between;
  padding: 5px 7px;
  background: rgb(0 0 0 / 10%);
  font-size: 10px;
}

.run-actions {
  gap: 7px;
  margin-top: 10px;
}

.no-run {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: var(--text-3);
  font-size: 10.5px;
}

.plan-steps h3 {
  margin-bottom: 8px;
}

.plan-steps > div {
  display: grid;
  grid-template-columns: 22px minmax(0, 1fr);
  gap: 2px 7px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border);
}

.plan-steps > div > span {
  grid-row: 1 / 3;
  color: var(--color-accent);
}

.plan-steps small {
  color: var(--text-3);
  font-size: 9.5px;
}

.empty {
  display: grid;
  flex: 1;
  place-items: center;
  padding: 20px;
  color: var(--text-3);
  text-align: center;
}

@media (width <= 1450px) {
  .mission-page {
    grid-template-columns: 195px minmax(400px, 1fr) 250px;
  }
}
</style>
