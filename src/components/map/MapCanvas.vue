<template>
  <div ref="mapContainer" class="map-container" :class="{ 'picking-cursor': pickingMode }">
    <div class="legend">
      <div><span class="dot online" />在线设备</div>
      <div><span class="dot dock" />坞站</div>
      <div><span class="dot selected" />当前选中</div>
      <div><span class="dot goal" />目标点</div>
      <div><span class="dot waypoint" />航点</div>
      <div><span class="trail-line" />历史轨迹</div>
    </div>
    <div class="hud mono">
      <div v-if="r?.position">
        {{ r.position.lat.toFixed(5) }} N · {{ r.position.lon.toFixed(5) }} E
      </div>
      <div v-else class="muted">未选中位置</div>
      <div v-if="goals.length" class="hud-goal">
        目标点: {{ goals.length }} 个
        <template v-if="r?.position"> | 最近: {{ nearestGoalDistance }}m</template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRobotsStore } from '@/stores/robots'
import { useSystemStore } from '@/stores/system'
import { isRobotConnected } from '@/utils/connection'
import { wgs84ToBd09, bd09ToWgs84, distanceM } from '@/utils/geo'
import { resolveInitialMapCenter } from '@/utils/map-center'
import type { GoalPoint } from '@/types'

interface Props {
  goals: GoalPoint[]
  waypoints: Array<{ lat: number; lon: number }>
  taskZone: { lat1: number; lon1: number; lat2: number; lon2: number } | null
  pickingMode: boolean
  robotPosition: { lat: number; lon: number } | null
}
const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'pick-point', lat: number, lon: number): void
  (e: 'goal-dragged', id: string, lat: number, lon: number): void
  (e: 'goal-removed', id: string): void
}>()

const robots = useRobotsStore()
const system = useSystemStore()
const r = computed(() => robots.selected)

const mapContainer = ref<HTMLDivElement | null>(null)

let map: BMapGL.Map | null = null

// 覆盖物引用
const markerMap = new Map<string, BMapGL.Marker>()
const polylineMap = new Map<string, BMapGL.Polyline>()
const goalMarkerMap = new Map<string, BMapGL.Marker>()
let goalPathLine: BMapGL.Polyline | null = null
const waypointMarkers: BMapGL.Marker[] = []

// 拖拽保护标志
let isDragging = false

// 选点模式监听函数引用
let pickClickHandler: ((e: any) => void) | null = null

/** 最近目标点与机器人的距离 */
const nearestGoalDistance = computed(() => {
  if (props.goals.length === 0 || !props.robotPosition) return '--'
  let minD = Infinity
  for (const g of props.goals) {
    const d = distanceM(props.robotPosition.lat, props.robotPosition.lon, g.lat, g.lon)
    if (d < minD) minD = d
  }
  return minD < 1000 ? Math.round(minD) : (minD / 1000).toFixed(2) + 'k'
})

/** 将 WGS-84 经纬度转为百度地图 Point */
function toBdPoint(lat: number, lon: number): BMapGL.Point {
  const bd = wgs84ToBd09(lon, lat)
  return new BMapGL.Point(bd.lng, bd.lat)
}

/** 创建带高对比度标签的机器人 Marker */
function createRobotMarker(id: string, lat: number, lon: number, isSelected: boolean, isOnline: boolean, isDock: boolean): BMapGL.Marker {
  const point = toBdPoint(lat, lon)
  const marker = new BMapGL.Marker(point, { enableDragging: false, title: id })
  let bgColor: string, borderColor: string
  if (isDock) {
    bgColor = isSelected ? 'rgba(59,130,246,0.88)' : 'rgba(245,158,11,0.88)'
    borderColor = isSelected ? '#60a5fa' : '#f59e0b'
  } else {
    bgColor = isSelected ? 'rgba(59,130,246,0.88)' : isOnline ? 'rgba(10,23,41,0.82)' : 'rgba(80,80,80,0.7)'
    borderColor = isSelected ? '#60a5fa' : isOnline ? '#3b82f6' : '#888'
  }
  const label = new BMapGL.Label(id, { offset: new BMapGL.Size(14, -6) })
  label.setStyle({
    background: bgColor, border: `1px solid ${borderColor}`, borderRadius: '4px',
    color: '#fff', fontSize: '12px', fontWeight: '600', padding: '2px 6px',
    lineHeight: '18px', boxShadow: '0 1px 4px rgba(0,0,0,0.4)', whiteSpace: 'nowrap'
  })
  marker.setLabel(label)
  return marker
}

/** 同步所有机器人标注 */
function syncRobotMarkers() {
  if (!map) return
  if (!system.backendConnected) {
    for (const marker of markerMap.values()) map.removeOverlay(marker)
    markerMap.clear()
    return
  }
  for (const [id, marker] of markerMap) {
    const robot = robots.getById(id)
    if (!robot || !robot.position) { map.removeOverlay(marker); markerMap.delete(id) }
  }
  for (const robot of robots.robots) {
    if (!robot.position) {
      const existing = markerMap.get(robot.id)
      if (existing && map) { map.removeOverlay(existing); markerMap.delete(robot.id) }
      continue
    }
    const isSel = robot.id === robots.selectedId
    const bdPoint = toBdPoint(robot.position.lat, robot.position.lon)
    const existing = markerMap.get(robot.id)
    if (existing) {
      existing.setPosition(bdPoint)
    } else {
      const marker = createRobotMarker(robot.id, robot.position.lat, robot.position.lon, isSel, system.backendConnected && isRobotConnected(robot), robot.robotType === 'dock')
      map.addOverlay(marker)
      markerMap.set(robot.id, marker)
    }
  }
}

/** 同步所有轨迹折线 */
function syncTrails() {
  if (!map) return
  for (const robot of robots.robots) {
    const existing = polylineMap.get(robot.id)
    if (!system.backendConnected || !isRobotConnected(robot) || robot.trail.length < 2) {
      if (existing && map) { map.removeOverlay(existing); polylineMap.delete(robot.id) }
      continue
    }
    const points = robot.trail.map(t => toBdPoint(t.lat, t.lon))
    const isSel = robot.id === robots.selectedId
    if (existing) {
      existing.setPath(points)
    } else {
      const polyline = new BMapGL.Polyline(points, {
        strokeColor: isSel ? '#3b82f6' : '#2ecc71', strokeWeight: isSel ? 2.5 : 1.5, strokeOpacity: isSel ? 0.9 : 0.6
      })
      map.addOverlay(polyline)
      polylineMap.set(robot.id, polyline)
    }
  }
}

/** 同步目标点标注（增量更新，支持拖拽保护） */
function syncGoals() {
  if (!map) return

  const currentIds = new Set(props.goals.map(g => g.id))

  // 移除已不存在的目标点标记
  for (const [id, marker] of goalMarkerMap) {
    if (!currentIds.has(id)) {
      map.removeOverlay(marker)
      goalMarkerMap.delete(id)
    }
  }

  // 新增或更新目标点标记
  for (let i = 0; i < props.goals.length; i++) {
    const goal = props.goals[i]
    const bdPoint = toBdPoint(goal.lat, goal.lon)
    const existing = goalMarkerMap.get(goal.id)

    if (existing) {
      // 标记已存在：仅在位置变化且非拖拽中时更新位置
      if (!isDragging) {
        const curPos = existing.getPosition()
        const eps = 1e-9
        if (Math.abs(curPos.lng - bdPoint.lng) > eps || Math.abs(curPos.lat - bdPoint.lat) > eps) {
          existing.setPosition(bdPoint)
        }
      }
      // 更新标签序号（删除目标点后序号会重排）
      const label = existing.getLabel()
      if (label) {
        label.setContent(`目标${i + 1}`)
      }
    } else {
      // 创建新标记
      const marker = new BMapGL.Marker(bdPoint, { enableDragging: true, title: `目标点 #${i + 1}` })
      const label = new BMapGL.Label(`目标${i + 1}`, { offset: new BMapGL.Size(14, -6) })
      label.setStyle({
        background: 'rgba(239,68,68,0.85)', border: '1px solid #ef4444', borderRadius: '4px',
        color: '#fff', fontSize: '11px', fontWeight: '600', padding: '2px 6px',
        lineHeight: '16px', boxShadow: '0 1px 4px rgba(0,0,0,0.4)', whiteSpace: 'nowrap'
      })
      marker.setLabel(label)

      const goalId = goal.id

      // 拖拽保护：开始拖拽时锁定
      marker.addEventListener('dragstart', () => { isDragging = true })

      // 拖拽结束后通知父组件更新坐标
      marker.addEventListener('dragend', () => {
        isDragging = false
        const pos = marker.getPosition()
        const wgs = bd09ToWgs84(pos.lng, pos.lat)
        emit('goal-dragged', goalId, wgs.lat, wgs.lng)
      })

      // 右键删除目标点
      marker.addEventListener('rightclick', () => {
        emit('goal-removed', goalId)
      })

      map.addOverlay(marker)
      goalMarkerMap.set(goal.id, marker)
    }
  }

  syncGoalLines()
}

/** 同步目标点链式路径连线：机器人→目标1→目标2→... */
function syncGoalLines() {
  if (!map) return

  // 移除旧连线
  if (goalPathLine) {
    map.removeOverlay(goalPathLine)
    goalPathLine = null
  }

  // 无目标点或无机器人位置时不绘制
  if (props.goals.length === 0 || !props.robotPosition) return

  // 构建链式路径点：机器人 → 目标1 → 目标2 → ...
  const points = [
    toBdPoint(props.robotPosition.lat, props.robotPosition.lon),
    ...props.goals.map(g => toBdPoint(g.lat, g.lon))
  ]

  goalPathLine = new BMapGL.Polyline(points, {
    strokeColor: '#9ca3af', strokeWeight: 1.5, strokeOpacity: 0.7, strokeStyle: 'dashed'
  })
  map.addOverlay(goalPathLine)
}

/** 同步航点标注 */
function syncWaypoints() {
  if (!map) return
  for (const m of waypointMarkers) { map.removeOverlay(m) }
  waypointMarkers.length = 0

  for (let i = 0; i < props.waypoints.length; i++) {
    const wpt = props.waypoints[i]
    const point = toBdPoint(wpt.lat, wpt.lon)
    const marker = new BMapGL.Marker(point, { title: `航点 #${i + 1}` })
    const label = new BMapGL.Label(`#${i + 1}`, { offset: new BMapGL.Size(10, -6) })
    label.setStyle({
      background: 'rgba(245,158,11,0.85)', border: '1px solid #f59e0b', borderRadius: '4px',
      color: '#fff', fontSize: '11px', fontWeight: '600', padding: '2px 5px',
      lineHeight: '16px', boxShadow: '0 1px 4px rgba(0,0,0,0.4)', whiteSpace: 'nowrap'
    })
    marker.setLabel(label)
    map.addOverlay(marker)
    waypointMarkers.push(marker)
  }
}

function syncAllOverlays() {
  syncRobotMarkers()
  syncTrails()
  syncGoals()
  syncWaypoints()
}

/** 切换地图类型（公开方法，由父组件调用） */
function setMapType(type: 'normal' | 'satellite' | 'earth') {
  if (!map) return
  switch (type) {
    case 'normal': map.setMapType(BMapGL.BMAP_NORMAL_MAP); break
    case 'satellite': map.setMapType(BMapGL.BMAP_SATELLITE_MAP); break
    case 'earth': map.setMapType(BMapGL.BMAP_EARTH_MAP); break
  }
}

/** 启用选点模式：监听地图点击 */
function enablePickingMode() {
  if (!map) return
  disablePickingMode() // 先清理
  pickClickHandler = (e: any) => {
    const bdLng = e.latlng?.lng
    const bdLat = e.latlng?.lat
    if (bdLng == null || bdLat == null) return
    const wgs = bd09ToWgs84(bdLng, bdLat)
    emit('pick-point', wgs.lat, wgs.lng)
  }
  map.addEventListener('click', pickClickHandler)
}

/** 禁用选点模式 */
function disablePickingMode() {
  if (!map || !pickClickHandler) return
  map.removeEventListener('click', pickClickHandler)
  pickClickHandler = null
}

defineExpose({ setMapType, enablePickingMode, disablePickingMode })

/** 初始化百度地图 */
function initMap() {
  const container = mapContainer.value
  if (!container) return

  const initialCenter = resolveInitialMapCenter(
    robots.sortedRobots,
    robots.selectedId,
    system.backendConnected
  )
  const center = toBdPoint(initialCenter.lat, initialCenter.lon)

  map = new BMapGL.Map(container, { minZoom: 3, maxZoom: 19 })
  map.centerAndZoom(center, 18)
  map.enableScrollWheelZoom(true)
  map.enableContinuousZoom()
  map.setMapType(BMapGL.BMAP_SATELLITE_MAP)

  try { map.addControl(new BMapGL.ScaleControl()) } catch (e) { console.warn('比例尺控件加载失败:', e) }
  try { map.addControl(new BMapGL.ZoomControl()) } catch (e) { console.warn('缩放控件加载失败:', e) }

  syncAllOverlays()
}

onMounted(() => {
  if (typeof BMapGL !== 'undefined') { initMap() }
  else {
    let tries = 0
    const timer = setInterval(() => {
      tries++
      if (typeof BMapGL !== 'undefined') { clearInterval(timer); initMap() }
      else if (tries > 50) { clearInterval(timer); console.error('百度地图 SDK 加载超时') }
    }, 100)
  }
})

onUnmounted(() => {
  disablePickingMode()
  markerMap.clear(); polylineMap.clear()
  goalMarkerMap.clear(); goalPathLine = null
  waypointMarkers.length = 0
  map = null
})

// 监听机器人数据变化
watch(
  () => ({ backend: system.backendConnected, robots: robots.robots.map(r => ({ id: r.id, pos: r.position, state: r.connection.state, trailLen: r.trail.length })) }),
  () => syncAllOverlays(), { deep: true }
)

// 监听选中变化，重建 marker 标签颜色 + 轨迹颜色 + 连线
watch(() => robots.selectedId, () => {
  if (map) {
    for (const [, marker] of markerMap) { map.removeOverlay(marker) }
    markerMap.clear()
    for (const [, polyline] of polylineMap) { map.removeOverlay(polyline) }
    polylineMap.clear()
  }
  syncRobotMarkers()
  syncTrails()
  syncGoalLines()
})

// 监听目标点和航点
watch(() => props.goals, () => syncGoals(), { deep: true })
watch(() => props.waypoints, () => syncWaypoints(), { deep: true })

// 监听机器人位置变化 → 更新连线
watch(() => props.robotPosition, () => syncGoalLines(), { deep: true })

// 监听选点模式
watch(() => props.pickingMode, (val) => {
  if (val) { enablePickingMode() } else { disablePickingMode() }
})
</script>

<style scoped>
.map-container {
  position: relative;
  width: 100%;
  height: 100%;
  border-radius: var(--radius-md);
  overflow: hidden;
}
.map-container.picking-cursor {
  cursor: crosshair;
}

.legend {
  position: absolute;
  top: 10px;
  right: 10px;
  background: rgba(0, 0, 0, 0.55);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 11.5px;
  color: var(--text-2);
  display: flex;
  flex-direction: column;
  gap: 4px;
  z-index: 10;
}
[data-theme='light'] .legend { background: rgba(255, 255, 255, 0.85); }
.legend .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }
.legend .dot.online { background: var(--color-online); }
.legend .dot.dock { background: var(--color-warn); }
.legend .dot.selected { background: var(--color-accent); box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3); }
.legend .dot.goal { background: transparent; border: 2px solid var(--color-danger); }
.legend .dot.waypoint { background: var(--color-warn); }
.legend .trail-line { display: inline-block; width: 14px; height: 0; border-top: 2px solid var(--color-accent); margin-right: 6px; vertical-align: middle; }
.hud {
  position: absolute;
  bottom: 10px;
  left: 12px;
  font-size: 11.5px;
  color: var(--text-2);
  background: rgba(0, 0, 0, 0.55);
  padding: 4px 8px;
  border-radius: 4px;
  border: 1px solid var(--border);
  z-index: 10;
}
[data-theme='light'] .hud { background: rgba(255, 255, 255, 0.85); }
.hud-goal {
  margin-top: 2px;
  color: #f87171;
}
</style>
