<template>
  <div class="map-page">
    <section class="map-area panel">
      <MapViewport
        :overlays="overlays"
        :picking="picking"
        @point-picked="addPickedPoint"
        @provider-ready="providerCapabilities = $event"
      />
      <div class="map-status">
        <StatusBadge
          :label="`${validDevicePositions.length} 个有效定位`"
          :tone="validDevicePositions.length ? 'success' : 'warning'"
        />
        <StatusBadge
          v-if="simulatedPositionCount"
          :label="`${simulatedPositionCount} 个仿真定位`"
          tone="simulation"
        />
      </div>
    </section>

    <section class="map-toolbar panel">
      <div class="toolbar-left">
        <el-button-group>
          <el-tooltip :content="pointPickingReason">
            <span>
              <el-button
                :icon="picking ? Close : Plus"
                :type="picking ? 'warning' : 'default'"
                :disabled="!canAddPoint"
                @click="picking = !picking"
              >
                {{ picking ? '取消选点' : '添加目标点' }}
              </el-button>
            </span>
          </el-tooltip>
          <el-button
            :icon="EditPen"
            :disabled="!fleet.selectedDevice"
            @click="openCoordinateDialog"
          >
            输入坐标
          </el-button>
          <el-button
            :icon="Delete"
            :disabled="!quickPoints.length || savingQuickMission"
            @click="clearQuickMission"
          >
            清除目标点
          </el-button>
          <el-button
            :icon="VideoPlay"
            type="primary"
            :disabled="!quickPlan || !fleet.selectedOnline || Boolean(activeRun)"
            :loading="startingRun"
            @click="startQuickMission"
          >
            开始导航
          </el-button>
          <el-button
            :icon="VideoPause"
            :disabled="activeRun?.status !== 'running'"
            @click="controlRun('pause')"
          >
            暂停
          </el-button>
          <el-button :icon="CircleClose" :disabled="!activeRun" @click="controlRun('cancel')">
            停止
          </el-button>
          <el-button
            :icon="Back"
            :disabled="!canReturnHome"
            :loading="returnCommand.submitting.value"
            @click="returnHome"
          >
            返航
          </el-button>
        </el-button-group>
        <el-button :icon="List" :disabled="!quickPoints.length" @click="pointsDrawerVisible = true">
          点位 {{ quickPoints.length }}
        </el-button>
        <el-button :icon="Compass" :disabled="!quickPlan" @click="openInMissions">
          在任务页打开
        </el-button>
      </div>

      <div class="toolbar-right">
        <el-tooltip :content="baseMapReason">
          <el-radio-group
            v-model="baseMap"
            size="small"
            :disabled="!providerCapabilities.baseMapSelection"
          >
            <el-radio-button value="satellite">卫星</el-radio-button>
            <el-radio-button value="normal">平面</el-radio-button>
          </el-radio-group>
        </el-tooltip>
        <span>路网</span>
        <el-tooltip :content="roadNetworkReason">
          <el-switch v-model="roadNetwork" :disabled="!providerCapabilities.roadNetwork" />
        </el-tooltip>
        <span class="hint">{{ toolbarHint }}</span>
      </div>
    </section>

    <el-dialog v-model="coordinateDialogVisible" title="输入 WGS-84 目标点" width="390px">
      <el-form label-width="65px">
        <el-form-item label="纬度">
          <el-input-number
            v-model="inputLatitude"
            :min="-90"
            :max="90"
            :precision="7"
            :controls="false"
          />
        </el-form-item>
        <el-form-item label="经度">
          <el-input-number
            v-model="inputLongitude"
            :min="-180"
            :max="180"
            :precision="7"
            :controls="false"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="coordinateDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingQuickMission" @click="confirmCoordinate">
          添加并同步任务
        </el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="pointsDrawerVisible" title="地图快捷任务点位" size="520px">
      <div class="quick-plan-summary">
        <div>
          <b>{{ quickPlan?.name ?? '尚未创建快捷任务' }}</b>
          <span v-if="quickPlan">v{{ quickPlan.version }} · {{ quickPlan.status }}</span>
        </div>
        <StatusBadge
          :label="savingQuickMission ? '正在同步' : quickPlan ? '已持久化' : '未创建'"
          :tone="savingQuickMission ? 'warning' : quickPlan ? 'success' : 'neutral'"
        />
      </div>
      <div class="point-list">
        <article
          v-for="(point, index) in quickPoints"
          :key="`${point.latitude}:${point.longitude}:${index}`"
        >
          <b>#{{ index + 1 }}</b>
          <div class="mono">
            <span>{{ point.latitude.toFixed(7) }}</span>
            <span>{{ point.longitude.toFixed(7) }}</span>
          </div>
          <el-button link type="primary" @click="editPoint(index)">编辑</el-button>
          <el-button link type="danger" :disabled="savingQuickMission" @click="removePoint(index)">
            删除
          </el-button>
        </article>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  Back,
  CircleClose,
  Close,
  Compass,
  Delete,
  EditPen,
  List,
  Plus,
  VideoPause,
  VideoPlay
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { MissionPlan, MissionPlanWrite, MissionRun } from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import { useMissionStore } from '@/entities/mission/store'
import { useCommand } from '@/features/commands/use-command'
import MapViewport from '@/features/map/MapViewport.vue'
import {
  isQuickMissionForDevice,
  quickMissionDescription,
  readQuickMissionId,
  writeQuickMissionId
} from '@/features/map/quick-mission-link'
import { hasCapability } from '@/shared/lib/device-view'
import type { MapOverlay, MapProviderCapabilities, Wgs84Coordinate } from '@/shared/map/types'
import StatusBadge from '@/shared/ui/StatusBadge.vue'

const emptyCapabilities: MapProviderCapabilities = {
  pointPicking: false,
  markerEditing: false,
  baseMapSelection: false,
  roadNetwork: false
}
const fleet = useFleetStore()
const missions = useMissionStore()
const router = useRouter()
const returnCommand = useCommand()
const providerCapabilities = ref<MapProviderCapabilities>({ ...emptyCapabilities })
const quickPoints = ref<Wgs84Coordinate[]>([])
const quickPlanId = ref<string | null>(null)
const picking = ref(false)
const savingQuickMission = ref(false)
const startingRun = ref(false)
const coordinateDialogVisible = ref(false)
const pointsDrawerVisible = ref(false)
const inputLatitude = ref<number | undefined>()
const inputLongitude = ref<number | undefined>()
const editingPointIndex = ref<number | null>(null)
const baseMap = ref<'satellite' | 'normal'>('satellite')
const roadNetwork = ref(false)

const quickPlan = computed(() =>
  quickPlanId.value ? (missions.plansById[quickPlanId.value] ?? null) : null
)
const activeRun = computed<MissionRun | null>(
  () =>
    missions.runs.find(
      (run) =>
        run.missionPlanId === quickPlanId.value &&
        ['queued', 'running', 'paused'].includes(run.status)
    ) ?? null
)
const validDevicePositions = computed(() =>
  fleet.devices.flatMap((device) => {
    const coordinate = deviceCoordinate(device.id)
    return coordinate ? [{ deviceId: device.id, coordinate }] : []
  })
)
const simulatedPositionCount = computed(
  () =>
    validDevicePositions.value.filter(
      ({ deviceId }) =>
        fleet.telemetryByDeviceId[deviceId]?.fields['position.latitude']?.quality === 'simulated'
    ).length
)
const overlays = computed<MapOverlay[]>(() => {
  const missionOverlays: MapOverlay[] = []
  if (quickPoints.value.length > 1) {
    missionOverlays.push({
      kind: 'polyline',
      id: `map-quick:${fleet.selectedDeviceId}`,
      coordinates: quickPoints.value,
      tone: '#f59e0b'
    })
  }
  quickPoints.value.forEach((coordinate, index) => {
    missionOverlays.push({
      kind: 'marker',
      id: `map-quick:${fleet.selectedDeviceId}:${index}`,
      coordinate,
      label: `目标点 #${index + 1}`,
      tone: '#f59e0b'
    })
  })
  const devices: MapOverlay[] = validDevicePositions.value.map(({ deviceId, coordinate }) => ({
    kind: 'marker',
    id: `device:${deviceId}`,
    coordinate,
    label: fleet.devicesById[deviceId]?.displayName ?? deviceId,
    tone:
      fleet.telemetryByDeviceId[deviceId]?.fields['position.latitude']?.quality === 'simulated'
        ? '#c084fc'
        : deviceId === fleet.selectedDeviceId
          ? '#38bdf8'
          : '#22c55e'
  }))
  return [...missionOverlays, ...devices]
})
const canAddPoint = computed(
  () =>
    Boolean(fleet.selectedDevice) &&
    providerCapabilities.value.pointPicking &&
    (hasCapability(fleet.selectedTemplate, 'mission.waypoint') ||
      hasCapability(fleet.selectedTemplate, 'mission.route')) &&
    !savingQuickMission.value
)
const canReturnHome = computed(
  () => fleet.selectedOnline && hasCapability(fleet.selectedTemplate, 'mission.return_home')
)
const pointPickingReason = computed(() => {
  if (!fleet.selectedDevice) return '请先选择设备'
  if (!providerCapabilities.value.pointPicking) return '当前地图引擎不可用或不支持地图选点'
  if (
    !hasCapability(fleet.selectedTemplate, 'mission.waypoint') &&
    !hasCapability(fleet.selectedTemplate, 'mission.route')
  )
    return '当前设备模板未声明目标点或路线任务能力'
  return '在地图上点击，点位会立即同步到后端快捷任务'
})
const baseMapReason = computed(() =>
  providerCapabilities.value.baseMapSelection
    ? '切换底图'
    : '当前地图适配器未声明安全的底图切换能力'
)
const roadNetworkReason = computed(() =>
  providerCapabilities.value.roadNetwork ? '切换路网覆盖' : '当前地图适配器未声明独立路网图层'
)
const toolbarHint = computed(() => {
  if (savingQuickMission.value) return '正在同步地图快捷任务…'
  if (picking.value) return '请在地图上点击 WGS-84 目标位置'
  if (!fleet.selectedDevice) return '请选择设备'
  if (!quickPoints.value.length) return '添加目标点后将创建后端 MissionPlan'
  return `快捷任务已持久化，共 ${quickPoints.value.length} 个点`
})

onMounted(loadQuickMission)
watch(
  () => fleet.selectedDeviceId,
  () => {
    picking.value = false
    void loadQuickMission()
  }
)

async function loadQuickMission(): Promise<void> {
  quickPoints.value = []
  quickPlanId.value = null
  const deviceId = fleet.selectedDeviceId
  if (!deviceId) return
  try {
    await missions.load()
    if (deviceId !== fleet.selectedDeviceId) return
    const mappedId = readQuickMissionId(deviceId)
    const candidate =
      (mappedId ? missions.plansById[mappedId] : null) ??
      missions.plans.find((plan) => isQuickMissionForDevice(plan.description, deviceId)) ??
      null
    if (!candidate) {
      writeQuickMissionId(deviceId, null)
      return
    }
    quickPlanId.value = candidate.id
    missions.selectedPlanId = candidate.id
    quickPoints.value = pointsFromPlan(candidate)
    writeQuickMissionId(deviceId, candidate.id)
  } catch {
    ElMessage.error('地图快捷任务读取失败')
  }
}

async function addPickedPoint(coordinate: Wgs84Coordinate): Promise<void> {
  picking.value = false
  await persistPoints([...quickPoints.value, coordinate])
}

function openCoordinateDialog(): void {
  editingPointIndex.value = null
  const selected = deviceCoordinate(fleet.selectedDeviceId)
  inputLatitude.value = selected?.latitude
  inputLongitude.value = selected?.longitude
  coordinateDialogVisible.value = true
}

function editPoint(index: number): void {
  const point = quickPoints.value[index]
  if (!point) return
  editingPointIndex.value = index
  inputLatitude.value = point.latitude
  inputLongitude.value = point.longitude
  coordinateDialogVisible.value = true
}

async function confirmCoordinate(): Promise<void> {
  if (
    inputLatitude.value == null ||
    inputLongitude.value == null ||
    !Number.isFinite(inputLatitude.value) ||
    !Number.isFinite(inputLongitude.value)
  ) {
    ElMessage.warning('请输入有效的 WGS-84 经纬度')
    return
  }
  const point = { latitude: inputLatitude.value, longitude: inputLongitude.value }
  const next = [...quickPoints.value]
  if (editingPointIndex.value == null) next.push(point)
  else next[editingPointIndex.value] = point
  if (await persistPoints(next)) coordinateDialogVisible.value = false
}

async function removePoint(index: number): Promise<void> {
  const next = quickPoints.value.filter((_, pointIndex) => pointIndex !== index)
  if (!next.length) await clearQuickMission()
  else await persistPoints(next)
}

async function persistPoints(points: Wgs84Coordinate[]): Promise<boolean> {
  const device = fleet.selectedDevice
  if (!device || savingQuickMission.value) return false
  if (points.length === 1 && !hasCapability(fleet.selectedTemplate, 'mission.waypoint')) {
    ElMessage.warning('当前设备模板未声明目标点任务能力')
    return false
  }
  if (points.length > 1 && !hasCapability(fleet.selectedTemplate, 'mission.route')) {
    ElMessage.warning('当前设备模板未声明路线任务能力，不能添加多个点')
    return false
  }
  savingQuickMission.value = true
  try {
    const body = quickMissionBody(device.id, device.displayName, points)
    const saved = quickPlanId.value
      ? await missions.update(quickPlanId.value, body)
      : await missions.create(body)
    quickPlanId.value = saved.id
    missions.selectedPlanId = saved.id
    quickPoints.value = pointsFromPlan(saved)
    writeQuickMissionId(device.id, saved.id)
    ElMessage.success(quickPlanId.value === saved.id ? '地图快捷任务已同步' : '快捷任务已创建')
    return true
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '地图快捷任务同步失败')
    return false
  } finally {
    savingQuickMission.value = false
  }
}

async function clearQuickMission(): Promise<void> {
  if (!quickPlan.value) {
    quickPoints.value = []
    return
  }
  try {
    await ElMessageBox.confirm('删除后端中的地图快捷任务及全部点位？', '清除目标点', {
      type: 'warning'
    })
    await missions.remove(quickPlan.value.id)
    writeQuickMissionId(fleet.selectedDeviceId, null)
    quickPlanId.value = null
    quickPoints.value = []
    pointsDrawerVisible.value = false
    ElMessage.success('地图快捷任务已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close')
      ElMessage.error(error instanceof Error ? error.message : '快捷任务删除失败')
  }
}

async function startQuickMission(): Promise<void> {
  if (!quickPlan.value || !fleet.selectedOnline) return
  startingRun.value = true
  try {
    const run = await missions.start(quickPlan.value.id)
    ElMessage.info(`任务运行 ${run.id} 已创建，状态：${run.status}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '任务启动失败')
  } finally {
    startingRun.value = false
  }
}

async function controlRun(action: 'pause' | 'cancel'): Promise<void> {
  if (!activeRun.value) return
  try {
    const receipt = await missions.control(activeRun.value.id, action)
    for (const command of receipt.commands) fleet.upsertCommand(command)
    ElMessage.info(`${action === 'pause' ? '暂停' : '取消'}请求已提交，等待设备确认`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '任务控制失败')
  }
}

async function returnHome(): Promise<void> {
  if (!canReturnHome.value) return
  const command = await returnCommand.submit(fleet.selectedDeviceId, 'return_home', {})
  if (command) ElMessage.info('返航请求已提交，等待设备确认')
}

function openInMissions(): void {
  if (quickPlan.value) missions.selectedPlanId = quickPlan.value.id
  void router.push('/mission')
}

function quickMissionBody(
  deviceId: string,
  displayName: string,
  points: Wgs84Coordinate[]
): MissionPlanWrite {
  const single = points.length === 1
  return {
    name: `地图快捷任务 · ${displayName}`,
    description: quickMissionDescription(deviceId),
    steps: [
      {
        id: single ? 'map-waypoint' : 'map-route',
        stepType: single ? 'waypoint' : 'route',
        deviceId,
        dependsOn: [],
        timeoutSeconds: 600,
        payload: single
          ? {
              latitude: points[0]?.latitude,
              longitude: points[0]?.longitude,
              coordinateReference: 'WGS-84'
            }
          : {
              waypoints: points.map((point) => ({
                latitude: point.latitude,
                longitude: point.longitude
              })),
              coordinateReference: 'WGS-84'
            }
      }
    ]
  }
}

function pointsFromPlan(plan: MissionPlan): Wgs84Coordinate[] {
  const step = plan.steps[0]
  if (!step) return []
  const payload = step.payload ?? {}
  if (step.stepType === 'waypoint') {
    const point = payloadCoordinate(payload)
    return point ? [point] : []
  }
  const waypoints = payload.waypoints
  return Array.isArray(waypoints)
    ? waypoints.flatMap((item) => {
        const point =
          item && typeof item === 'object'
            ? payloadCoordinate(item as Record<string, unknown>)
            : null
        return point ? [point] : []
      })
    : []
}

function payloadCoordinate(payload: Record<string, unknown>): Wgs84Coordinate | null {
  return typeof payload.latitude === 'number' && typeof payload.longitude === 'number'
    ? { latitude: payload.latitude, longitude: payload.longitude }
    : null
}

function deviceCoordinate(deviceId: string): Wgs84Coordinate | null {
  const fields = fleet.telemetryByDeviceId[deviceId]?.fields
  const latitude = fields?.['position.latitude']
  const longitude = fields?.['position.longitude']
  if (
    !latitude ||
    !longitude ||
    !['valid', 'simulated'].includes(latitude.quality) ||
    !['valid', 'simulated'].includes(longitude.quality) ||
    typeof latitude.value !== 'number' ||
    typeof longitude.value !== 'number'
  )
    return null
  return { latitude: latitude.value, longitude: longitude.value }
}
</script>

<style scoped>
.map-page {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
  min-height: 0;
}

.map-area {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.map-area :deep(.map-viewport) {
  min-height: 100%;
}

.map-status {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 4;
  display: flex;
  gap: 6px;
}

.map-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex: 0 0 auto;
  min-height: 50px;
  padding: 8px 12px;
}

.toolbar-left,
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
}

.toolbar-right {
  flex: 0 0 auto;
  color: var(--text-2);
}

.hint {
  max-width: 265px;
  overflow: hidden;
  color: var(--text-3);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.coordinate-dialog :deep(.el-input-number),
.el-form-item :deep(.el-input-number) {
  width: 100%;
}

.quick-plan-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel-2);
}

.quick-plan-summary div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.quick-plan-summary span {
  color: var(--text-3);
  font-size: 10px;
}

.point-list {
  display: flex;
  flex-direction: column;
  gap: 7px;
  margin-top: 12px;
}

.point-list article {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  padding: 9px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.point-list article > div {
  display: flex;
  flex-direction: column;
  color: var(--text-2);
  font-size: 10px;
}

@media (width <= 1450px) {
  .toolbar-left {
    gap: 5px;
  }

  .toolbar-right .hint {
    display: none;
  }
}
</style>
