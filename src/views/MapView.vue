<template>
  <div class="map-view">
    <div class="map-area">
      <MapCanvas
        ref="mapCanvasRef"
        :goals="goals"
        :waypoints="waypoints"
        :task-zone="taskZone"
        :picking-mode="pickingMode"
        :robot-position="system.backendConnected ? (selected?.position ?? null) : null"
        @pick-point="onPickPoint"
        @goal-dragged="onGoalDragged"
        @goal-removed="onGoalRemoved"
      />
    </div>
    <MapToolbar
      :has-goal="goals.length > 0"
      :goal-count="goals.length"
      :can-control="canControl"
      :base-map="baseMap"
      :show-road-net="showRoadNet"
      :picking-mode="pickingMode"
      @enter-pick-mode="pickingMode = true"
      @cancel-pick-mode="pickingMode = false"
      @input-coords="inputDialogVisible = true"
      @send-goal="sendGoal"
      @clear-goals="clearGoals"
      @start="startNav"
      @pause="pauseNav"
      @stop="stopNav"
      @return="returnHome"
      @clear-trail="clearTrail"
      @switch-base-map="onSwitchBaseMap"
      @toggle-road-net="onToggleRoadNet"
    />

    <!-- 输入坐标对话框 -->
    <el-dialog v-model="inputDialogVisible" title="输入目标点坐标" width="380px" :close-on-click-modal="false">
      <el-form label-width="60px">
        <el-form-item label="纬度">
          <el-input-number v-model="inputLat" :precision="6" :step="0.0001" :controls="false" style="width: 100%" />
        </el-form-item>
        <el-form-item label="经度">
          <el-input-number v-model="inputLon" :precision="6" :step="0.0001" :controls="false" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="inputDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="onConfirmInput">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import MapCanvas from '@/components/map/MapCanvas.vue'
import MapToolbar from '@/components/map/MapToolbar.vue'
import { useRobotsStore } from '@/stores/robots'
import { useLogsStore } from '@/stores/logs'
import {
  postNavigationPause,
  postNavigationResume,
  postNavigationReturnHome,
  postNavigationStart,
  postNavigationStop
} from '@/services/backend-api'
import { distanceM } from '@/utils/geo'
import type { GoalPoint } from '@/types'
import { useSystemStore } from '@/stores/system'
import { hasCommandChannel } from '@/utils/connection'

const robots = useRobotsStore()
const logs = useLogsStore()
const system = useSystemStore()

const mapCanvasRef = ref<InstanceType<typeof MapCanvas> | null>(null)

/** 底图类型 */
const baseMap = ref<'satellite' | 'normal'>('satellite')
/** 路网开关 */
const showRoadNet = ref(false)
/** 选点模式 */
const pickingMode = ref(false)

/** 目标点列表 */
const goals = ref<GoalPoint[]>([])
const waypoints = ref<Array<{ lat: number; lon: number }>>([])
const taskZone = ref({ lat1: 30.3155, lon1: 120.3490, lat2: 30.3185, lon2: 120.3540 })

/** 坐标输入对话框 */
const inputDialogVisible = ref(false)
const inputLat = ref(30.3168)
const inputLon = ref(120.3505)

const selected = computed(() => robots.selected)
const canControl = computed(() => system.backendConnected && hasCommandChannel(selected.value))

function ensureSelected(): boolean {
  if (!selected.value) { ElMessage.warning('请先选择一个设备'); return false }
  if (!system.backendConnected) { ElMessage.warning('后端连接中断，无法控制'); return false }
  if (!canControl.value) { ElMessage.warning('设备未连接或操作通道不可用'); return false }
  return true
}

/** 格式化距离 */
function fmtDist(d: number): string {
  return d < 1000 ? `${Math.round(d)}m` : `${(d / 1000).toFixed(2)}km`
}

/** 添加目标点并记录日志 */
function addGoal(lat: number, lon: number) {
  const id = crypto.randomUUID()
  goals.value.push({ id, lat, lon, speed: 0 })
  const r = selected.value
  const distStr = r?.position ? ` (${fmtDist(distanceM(r.position.lat, r.position.lon, lat, lon))})` : ''
  logs.append('操作', r?.id ?? null, `已添加目标点 #${goals.value.length} (${lat.toFixed(5)}, ${lon.toFixed(5)})${distStr}`)
}

/** 按 ID 移除目标点 */
function removeGoal(id: string) {
  const idx = goals.value.findIndex(g => g.id === id)
  if (idx !== -1) {
    const g = goals.value[idx]
    goals.value.splice(idx, 1)
    logs.append('操作', selected.value?.id ?? null, `已移除目标点 (${g.lat.toFixed(5)}, ${g.lon.toFixed(5)})`)
  }
}

/** 清除所有目标点 */
function clearGoals() {
  if (goals.value.length === 0) return
  const count = goals.value.length
  goals.value = []
  logs.append('操作', selected.value?.id ?? null, `已清除 ${count} 个目标点`)
}

/** 按 ID 更新目标点位置 */
function updateGoalPosition(id: string, lat: number, lon: number) {
  const goal = goals.value.find(g => g.id === id)
  if (goal) {
    goal.lat = lat
    goal.lon = lon
    const r = selected.value
    const distStr = r?.position ? ` (${fmtDist(distanceM(r.position.lat, r.position.lon, lat, lon))})` : ''
    logs.append('操作', r?.id ?? null, `目标点已拖拽至 (${lat.toFixed(5)}, ${lon.toFixed(5)})${distStr}`)
  }
}

/** 地图点击选点回调 */
function onPickPoint(lat: number, lon: number) {
  pickingMode.value = false
  addGoal(lat, lon)
}

/** 目标点拖拽回调 */
function onGoalDragged(id: string, lat: number, lon: number) {
  updateGoalPosition(id, lat, lon)
}

/** 目标点右键删除回调 */
function onGoalRemoved(id: string) {
  removeGoal(id)
}

/** 坐标输入确认 */
function onConfirmInput() {
  if (inputLat.value == null || inputLon.value == null) {
    ElMessage.warning('请输入有效的经纬度')
    return
  }
  inputDialogVisible.value = false
  addGoal(inputLat.value, inputLon.value)
}

/** 底图 + 路网组合 */
function applyMapType() {
  let type: 'normal' | 'satellite' | 'earth'
  if (baseMap.value === 'normal') { type = 'normal' }
  else { type = showRoadNet.value ? 'earth' : 'satellite' }
  mapCanvasRef.value?.setMapType(type)
}

function onSwitchBaseMap(...args: any[]) {
  baseMap.value = args[0] as 'satellite' | 'normal'
  applyMapType()
}

function onToggleRoadNet(...args: any[]) {
  showRoadNet.value = !!args[0]
  applyMapType()
}

async function sendGoal() {
  if (!ensureSelected() || goals.value.length === 0) return
  const r = selected.value!
  const goalDesc = goals.value.length === 1
    ? `(${goals.value[0].lat.toFixed(5)}, ${goals.value[0].lon.toFixed(5)})`
    : `${goals.value.length} 个目标点`
  logs.append('操作', r.id, `下发目标点 ${goalDesc}`)
  try {
    const updated = await postNavigationStart(r.id, goals.value)
    robots.applyRobot(updated)
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端目标点下发失败')
  }
}

async function startNav() {
  if (!ensureSelected()) return
  const r = selected.value!
  try {
    const updated = goals.value.length > 0 && r.navState === 'idle'
      ? await postNavigationStart(r.id, goals.value)
      : await postNavigationResume(r.id)
    robots.applyRobot(updated)
    logs.append('操作', r.id, '开始导航')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端开始导航失败')
  }
}

async function pauseNav() {
  if (!ensureSelected()) return
  const r = selected.value!
  try {
    const updated = await postNavigationPause(r.id)
    robots.applyRobot(updated)
    logs.append('操作', r.id, '暂停导航')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端暂停任务失败')
  }
}

async function stopNav() {
  if (!ensureSelected()) return
  const r = selected.value!
  try {
    const updated = await postNavigationStop(r.id)
    robots.applyRobot(updated)
    logs.append('操作', r.id, '停止导航')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端停止任务失败')
  }
}

async function returnHome() {
  if (!ensureSelected()) return
  const r = selected.value!
  try {
    const updated = await postNavigationReturnHome(r.id)
    robots.applyRobot(updated)
    logs.append('操作', r.id, '返航指令已发送')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端返航失败')
  }
}

function clearTrail() {
  const r = selected.value
  if (!r) return
  ElMessage.info('轨迹由后端统一维护，当前版本暂不支持手工清除')
}

// 选点模式变化时通知 MapCanvas
watch(pickingMode, (val) => {
  if (val) { mapCanvasRef.value?.enablePickingMode() }
  else { mapCanvasRef.value?.disablePickingMode() }
})

// ESC 取消选点模式
function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && pickingMode.value) {
    pickingMode.value = false
  }
}
watch(pickingMode, (val) => {
  if (val) { window.addEventListener('keydown', onKeydown) }
  else { window.removeEventListener('keydown', onKeydown) }
}, { immediate: true })
</script>

<style scoped>
.map-view {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}
.map-area {
  flex: 1;
  min-height: 0;
}
</style>
