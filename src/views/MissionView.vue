<template>
  <div class="mission">
    <div class="mission-grid">
      <div class="left panel">
        <div class="section-title">任务类型</div>
        <div class="task-types">
          <div
            v-for="t in taskTypes"
            :key="t.value"
            class="task-type"
            :class="{ active: tab === t.value }"
            @click="tab = t.value"
          >
            <el-icon><component :is="t.icon" /></el-icon>
            <div class="meta">
              <div class="name">{{ t.label }}</div>
              <div class="desc">{{ t.desc }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="middle panel">
        <div class="section-title">{{ currentLabel ? currentLabel + ' · 配置' : '任务配置' }}</div>

        <!-- 坞站无可用任务 -->
        <div v-if="taskTypes.length === 0" class="form">
          <div class="charging-desc muted">
            该设备为智能坞站，无可执行的任务类型。
          </div>
        </div>

        <!-- 目标点任务 -->
        <div v-if="tab === 'goal'" class="form">
          <el-form label-width="100px" label-position="left" size="default">
            <el-form-item label="目标纬度">
              <el-input-number v-model="goal.lat" :precision="5" :step="0.0001" :controls="false" style="width: 200px" />
            </el-form-item>
            <el-form-item label="目标经度">
              <el-input-number v-model="goal.lon" :precision="5" :step="0.0001" :controls="false" style="width: 200px" />
            </el-form-item>
            <el-form-item label="目标速度">
              <el-input-number v-model="goal.speed" :precision="2" :step="0.1" :min="0" :max="2" style="width: 200px" />
              <span class="muted" style="margin-left: 8px">m/s</span>
            </el-form-item>
          </el-form>
          <div class="action-row">
            <el-button :icon="Promotion" :disabled="!canControl" @click="onSendGoal">下发目标点</el-button>
            <el-button :icon="VideoPlay" type="primary" :disabled="!canControl" @click="onStart">开始任务</el-button>
            <el-button :icon="VideoPause" :disabled="!canControl" @click="onPause">暂停任务</el-button>
            <el-button :icon="CircleClose" :disabled="!canControl" @click="onStop">停止任务</el-button>
          </div>
        </div>

        <!-- 路线任务 -->
        <div v-else-if="tab === 'route'" class="form">
          <el-table :data="route.waypoints" size="small" border style="margin-bottom: 12px">
            <el-table-column type="index" label="#" width="50" />
            <el-table-column label="纬度" width="160">
              <template #default="{ row }: { row: Waypoint }">
                <el-input-number v-model="row.lat" :precision="5" :step="0.0001" :controls="false" />
              </template>
            </el-table-column>
            <el-table-column label="经度" width="160">
              <template #default="{ row }: { row: Waypoint }">
                <el-input-number v-model="row.lon" :precision="5" :step="0.0001" :controls="false" />
              </template>
            </el-table-column>
            <el-table-column label="速度 m/s" width="140">
              <template #default="{ row }: { row: Waypoint }">
                <el-input-number v-model="row.speed" :precision="2" :step="0.1" :min="0" :max="2" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ $index }: { $index: number }">
                <el-button link type="danger" :icon="Delete" @click="removeWaypoint($index)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-form inline label-position="left" label-width="80px">
            <el-form-item label="是否循环">
              <el-switch v-model="route.loop" />
            </el-form-item>
            <el-form-item label="巡航速度">
              <el-input-number v-model="route.cruiseSpeed" :precision="2" :step="0.1" :min="0" :max="2" />
              <span class="muted" style="margin-left: 6px">m/s</span>
            </el-form-item>
          </el-form>
          <div class="action-row">
            <el-button :icon="Plus" @click="addWaypoint">添加航点</el-button>
            <el-button :icon="Promotion" :disabled="!canControl || !route.waypoints.length" @click="onSendRoute">下发路线</el-button>
          </div>
        </div>

        <!-- 自主返航充电任务 -->
        <div v-else-if="tab === 'charging'" class="form">
          <div class="charging-desc muted">
            无人机将自主返航至无人船，降落并开启无线能源补给。
          </div>
          <div class="action-row">
            <el-button type="primary" :icon="VideoPlay" :disabled="!canControl || chargingPhase !== 'idle'" @click="onChargingStart">开始任务</el-button>
            <el-button :icon="CircleClose" :disabled="!canControl || chargingPhase === 'idle'" @click="onChargingStop">停止任务</el-button>
          </div>
          <div class="action-row">
            <el-button :icon="Lightning" :disabled="!canControl || chargingPhase !== 'allow_charge'" @click="onChargingBegin">开始充电</el-button>
            <el-button :icon="SwitchButton" :disabled="!canControl || chargingPhase !== 'charging'" @click="onChargingHalt">停止充电</el-button>
          </div>
          <div class="action-row">
            <el-button :icon="Unlock" :disabled="!canControl || !canUnlockAircraft" @click="onUnlockAircraft">解锁飞机</el-button>
          </div>
        </div>

        <!-- 垃圾收集任务 -->
        <div v-else-if="tab === 'collect'" class="form">
          <div class="charging-desc muted">
            无人船将在划分的 16 个区域中逐区扫描并自动清理水面垃圾。
          </div>
          <div class="action-row">
            <el-button type="primary" :icon="VideoPlay" :disabled="!canControl || collectPhase !== 'idle'" @click="onCollectStart">开始任务</el-button>
            <el-button :icon="VideoPause" :disabled="!canControl || collectPhase !== 'running'" @click="onCollectPause">暂停任务</el-button>
            <el-button :icon="CircleClose" :disabled="!canControl || collectPhase === 'idle'" @click="onCollectStop">停止任务</el-button>
          </div>
        </div>

        <!-- 简单动作 -->
        <div v-else class="form">
          <div class="action-grid">
            <el-button class="simple-action-button" size="large" :icon="Back" :disabled="!canControl" @click="onAction('返航')">返航</el-button>
            <el-button class="simple-action-button" size="large" :icon="CircleClose" :disabled="!canControl" @click="onAction('原地停止')">原地停止</el-button>
            <el-button class="simple-action-button" size="large" :icon="RefreshRight" :disabled="!canControl" @click="onAction('复位设备')">复位设备</el-button>
            <el-button class="simple-action-button" size="large" :icon="VideoCameraFilled" :disabled="!canControl" @click="onAction('打开载荷')">打开载荷</el-button>
            <el-button class="simple-action-button" size="large" :icon="VideoCamera" :disabled="!canControl" @click="onAction('关闭载荷')">关闭载荷</el-button>
            <el-button
              v-if="isClUsv"
              data-testid="electromagnetic-fix-button"
              class="simple-action-button"
              :class="{ 'relay-active': r?.relayEnabled === true }"
              size="large"
              :type="r?.relayEnabled === true ? 'danger' : 'default'"
              :loading="relayChanging"
              :disabled="!canToggleRelay"
              @click="onToggleRelay"
            >
              {{ relayButtonText }}
            </el-button>
            <el-button
              v-if="isClUsv"
              data-testid="wireless-charge-button"
              class="simple-action-button"
              size="large"
              :loading="wirelessChargingChecking"
              :disabled="!canControl || wirelessChargingChecking"
              @click="onWirelessChargingToggle"
            >
              {{ wirelessChargingChecking ? '无线充电：检测中' : '无线充电：关' }}
            </el-button>
          </div>
        </div>
      </div>

      <div class="right panel">
        <div class="section-title">任务执行状态</div>
        <div v-if="!r" class="muted">未选中设备</div>
        <div v-else class="status">
          <div class="kv-row">
            <span class="k">设备</span>
            <span class="v mono">{{ r.id }}</span>
          </div>
          <div class="kv-row">
            <span class="k">控制模式</span>
            <span class="v">
              <span class="tag-pill" :class="modeTone">{{ dataAvailable ? (r.mode ?? '未知') : '未知' }}</span>
            </span>
          </div>
          <div class="kv-row">
            <span class="k">任务状态</span>
            <span class="v">{{ canControl ? (r.missionStatus ?? '未知') : '未知' }}</span>
          </div>
          <div class="kv-row">
            <span class="k">速度</span>
            <span class="v mono">{{ formatNum(dataAvailable ? r.speed : null, 'm/s', 2) }}</span>
          </div>
          <div class="kv-row">
            <span class="k">位置</span>
            <span class="v mono">{{ formatPos(dataAvailable ? r.position : null) }}</span>
          </div>

          <div class="progress-block">
            <div class="progress-label">
              <span>任务进度</span>
              <span class="mono">{{ displayProgress }}%</span>
            </div>
            <el-progress :percentage="displayProgress" :stroke-width="8" :show-text="false" />
          </div>

          <!-- 充电任务滚动日志 -->
          <div v-if="tab === 'charging' && chargingLogs.length > 0" ref="chargingLogRef" class="scroll-log">
            <div v-for="(log, i) in chargingLogs" :key="i" class="log-line">{{ log }}</div>
          </div>
          <!-- 垃圾收集任务滚动日志 -->
          <div v-else-if="tab === 'collect' && collectLogs.length > 0" ref="collectLogRef" class="scroll-log">
            <div v-for="(log, i) in collectLogs" :key="i" class="log-line">{{ log }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, markRaw, nextTick, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Aim,
  Promotion,
  VideoPlay,
  VideoPause,
  CircleClose,
  Plus,
  Delete,
  Back,
  RefreshRight,
  VideoCamera,
  VideoCameraFilled,
  Compass,
  Operation,
  Lightning,
  SwitchButton,
  Unlock,
  Delete as DeleteIcon
} from '@element-plus/icons-vue'
import { useRobotsStore } from '@/stores/robots'
import { useLogsStore } from '@/stores/logs'
import {
  postElectromagneticFix,
  postLockCommand,
  postModeCommand,
  postNavigationPause,
  postNavigationResume,
  postNavigationReturnHome,
  postNavigationStart,
  postNavigationStop
} from '@/services/backend-api'
import type { Robot, Waypoint } from '@/types'
import { useSystemStore } from '@/stores/system'
import { hasCommandChannel, hasUsableDataChannel, isRobotConnected } from '@/utils/connection'

const robots = useRobotsStore()
const logs = useLogsStore()
const system = useSystemStore()
const r = computed(() => robots.selected)
const dataAvailable = computed(() => system.backendConnected && hasUsableDataChannel(r.value))
const canControl = computed(() => system.backendConnected && hasCommandChannel(r.value))
const isClUsv = computed(() => r.value?.id === 'CL-USV')
const relayChanging = ref(false)
const wirelessChargingChecking = ref(false)
let wirelessChargeTimer: ReturnType<typeof setTimeout> | null = null
const relayButtonText = computed(() => {
  if (r.value?.relayEnabled === true) return '电磁固定：开'
  if (r.value?.relayEnabled === false) return '电磁固定：关'
  return '电磁固定：状态未知'
})
const canToggleRelay = computed(() => Boolean(
  isClUsv.value
  && canControl.value
  && r.value?.connection.activeMethod === 'network'
  && r.value.connection.dataMode === 'live'
  && typeof r.value.relayEnabled === 'boolean'
  && !relayChanging.value
))

type TaskTab = 'goal' | 'route' | 'charging' | 'collect' | 'action'
const tab = ref<TaskTab>('goal')
const allTaskTypes = [
  { value: 'goal' as const, label: '目标点任务', desc: '飞往指定坐标', icon: markRaw(Aim) },
  { value: 'route' as const, label: '路线任务', desc: '按航点顺序巡航', icon: markRaw(Compass) },
  { value: 'charging' as const, label: '自主返航充电', desc: '降落船体 · 无线补电', icon: markRaw(Lightning) },
  { value: 'collect' as const, label: '垃圾收集任务', desc: '区域扫描 · 自动清理', icon: markRaw(DeleteIcon) },
  { value: 'action' as const, label: '简单动作', desc: '返航 / 复位 / 载荷', icon: markRaw(Operation) }
]

// 按设备类型过滤可用任务
const taskTypes = computed(() => {
  const type = r.value?.robotType
  if (type === 'dock') return [] // 坞站无可执行任务
  if (type === 'uav') {
    // 无人机：目标点、路线、返航充电、简单动作
    return allTaskTypes.filter(t => t.value !== 'collect')
  }
  if (type === 'usv') {
    // CL-USV 不具备垃圾回收能力，另一艘无人船保持原任务集合。
    return allTaskTypes.filter(t => (
      t.value !== 'charging'
      && !(r.value?.id === 'CL-USV' && t.value === 'collect')
    ))
  }
  return allTaskTypes
})
const currentLabel = computed(() => taskTypes.value.find(t => t.value === tab.value)?.label ?? '')

// 切换设备时重置 tab 到第一个可用任务
watch(() => r.value?.id, () => {
  if (taskTypes.value.length > 0 && !taskTypes.value.find(t => t.value === tab.value)) {
    tab.value = taskTypes.value[0].value
  }
})

const goal = ref({ lat: 30.2755, lon: 120.157, speed: 0.6 })
const route = ref<{ waypoints: Waypoint[]; loop: boolean; cruiseSpeed: number }>({
  waypoints: [
    { index: 1, lat: 30.2738, lon: 120.1545, speed: 0.5 },
    { index: 2, lat: 30.2755, lon: 120.1572, speed: 0.6 },
    { index: 3, lat: 30.277, lon: 120.1595, speed: 0.5 }
  ],
  loop: false,
  cruiseSpeed: 0.6
})

const modeTone = computed(() => {
  if (!dataAvailable.value) return 'offline'
  switch (r.value?.mode) {
    case '手动':
      return 'info'
    case '自动':
      return 'online'
    case '急停':
      return 'danger'
    default:
      return 'offline'
  }
})

// ─── 通用工具 ───

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v))
}

function ensureCanControl(): boolean {
  if (!canControl.value) {
    if (!system.backendConnected) ElMessage.warning('后端连接中断，无法控制')
    else if (!isRobotConnected(r.value)) ElMessage.warning('设备未连接，无法控制')
    else ElMessage.warning('当前连接尚无可用操作通道')
    return false
  }
  return true
}

/** 滚动日志容器到底部 */
function scrollLogToBottom(el: HTMLElement | null) {
  if (el) el.scrollTop = el.scrollHeight
}

// ─── 导航任务进度 ───
const navProgress = computed(() => {
  if (!r.value) return 0
  const robot = r.value
  if (robot.navGoals.length === 0) {
    if (robot.missionStatus === '空闲' || robot.missionStatus === '无任务' || robot.missionStatus === '急停') return 0
    return 0
  }
  const completed = robot.navGoalIndex
  const total = robot.navGoals.length
  if (robot.navState === 'idle') return 100
  return Math.round((completed / total) * 100)
})

// 根据当前任务类型选择进度源
const displayProgress = computed(() => {
  if (tab.value === 'charging') return chargingProgress.value
  if (tab.value === 'collect') return collectProgress.value
  return navProgress.value
})

// ─── 充电状态机 ───
type ChargingPhase = 'idle' | 'locating' | 'landing' | 'landed' | 'fixing' | 'evaluating' | 'aligned' | 'allow_charge' | 'charging'

const chargingPhase = ref<ChargingPhase>('idle')
const chargingLogs = ref<string[]>([])
const chargingProgress = ref(0)
const chargingTimers = ref<ReturnType<typeof setTimeout>[]>([])
const chargingLoopTimer = ref<ReturnType<typeof setInterval> | null>(null)
const lastPower = ref(45)
const lastEfficiency = ref(67)
const chargingLogRef = ref<HTMLElement | null>(null)

function randomDelay(): number {
  return 1000 + Math.random() * 1000
}

function pushChargingLog(text: string) {
  chargingLogs.value.push(text)
  nextTick(() => scrollLogToBottom(chargingLogRef.value))
}

function clearChargingTimers() {
  chargingTimers.value.forEach(t => clearTimeout(t))
  chargingTimers.value = []
  if (chargingLoopTimer.value !== null) {
    clearInterval(chargingLoopTimer.value)
    chargingLoopTimer.value = null
  }
}

function resetChargingState() {
  clearChargingTimers()
  chargingPhase.value = 'idle'
  chargingLogs.value = []
  chargingProgress.value = 0
}

async function onChargingStart() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    robots.applyRobot(await postNavigationReturnHome(robot.id))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '返航充电任务启动失败')
    return
  }
  resetChargingState()

  const steps: { phase: ChargingPhase; text: string; progress: number }[] = [
    { phase: 'locating', text: '正在定位无人船....', progress: 5 },
    { phase: 'landing', text: '正在降落....', progress: 15 },
    { phase: 'landed', text: '降落成功', progress: 30 },
    { phase: 'fixing', text: '电磁固定已开启.....', progress: 40 },
    { phase: 'evaluating', text: '评估线圈对齐程度中.....', progress: 50 },
    { phase: 'aligned', text: '', progress: 60 },
    { phase: 'allow_charge', text: '允许开启无线能源补给...', progress: 70 },
    { phase: 'charging', text: '已经开启能源补给....', progress: 80 }
  ]

  let acc = 0
  steps.forEach((step) => {
    acc += randomDelay()
    const delay = acc
    const timer = setTimeout(() => {
      if (step.phase === 'aligned') {
        const alignment = +(60 + Math.random() * 10).toFixed(1)
        step.text = `线圈对齐程度：${alignment}%`
      }
      chargingPhase.value = step.phase
      chargingProgress.value = step.progress
      pushChargingLog(step.text)
      if (step.phase === 'charging') startChargingLoop()
    }, delay)
    chargingTimers.value.push(timer)
  })

  logs.append('操作', robot.id, '开始自主返航充电任务')
}

function startChargingLoop() {
  if (chargingLoopTimer.value !== null) return
  chargingLoopTimer.value = setInterval(() => {
    const power = +clamp(lastPower.value + (Math.random() - 0.5) * 2, 40, 50).toFixed(1)
    const eff = +clamp(lastEfficiency.value + (Math.random() - 0.5) * 2, 65, 70).toFixed(1)
    lastPower.value = power
    lastEfficiency.value = eff
    pushChargingLog(`能源补给中，当前功率${power}W，效率${eff}%`)
    if (chargingProgress.value < 95) {
      chargingProgress.value = Math.min(95, chargingProgress.value + Math.floor(1 + Math.random() * 2))
    }
  }, 2000)
}

async function onChargingHalt() {
  if (!ensureCanControl()) return
  try {
    robots.applyRobot(await postNavigationPause(r.value!.id))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '暂停充电任务失败')
    return
  }
  if (chargingLoopTimer.value !== null) {
    clearInterval(chargingLoopTimer.value)
    chargingLoopTimer.value = null
  }
  chargingPhase.value = 'allow_charge'
  pushChargingLog('能源补给已暂停')
  logs.append('操作', r.value!.id, '停止充电')
}

async function onChargingBegin() {
  if (!ensureCanControl()) return
  try {
    robots.applyRobot(await postNavigationResume(r.value!.id))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '恢复充电任务失败')
    return
  }
  chargingPhase.value = 'charging'
  pushChargingLog('已经开启能源补给....')
  startChargingLoop()
  logs.append('操作', r.value!.id, '开始充电')
}

async function onChargingStop() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    robots.applyRobot(await postNavigationStop(robot.id))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '停止充电任务失败')
    return
  }
  resetChargingState()
  logs.append('操作', robot.id, '停止自主返航充电任务')
}

const canUnlockAircraft = computed(() => {
  return chargingPhase.value === 'landed' ||
    chargingPhase.value === 'fixing' ||
    chargingPhase.value === 'evaluating' ||
    chargingPhase.value === 'aligned' ||
    chargingPhase.value === 'allow_charge' ||
    chargingPhase.value === 'charging'
})

async function onUnlockAircraft() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    robots.applyRobot(await postLockCommand(robot.id, true))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '飞机解锁失败')
    return
  }
  pushChargingLog('飞机已解锁')
  ElMessage.success('解锁指令发送成功')
  logs.append('操作', robot.id, '解锁飞机指令已发送')
}

// ─── 垃圾收集状态机 ───
type CollectPhase = 'idle' | 'running' | 'paused' | 'completed'

const TOTAL_AREAS = 16
const AREA_DURATION_MS = 60000     // 每个区域 60s
const REPORT_INTERVAL_MS = 5000    // 5s 播报

const collectPhase = ref<CollectPhase>('idle')
const collectLogs = ref<string[]>([])
const collectProgress = ref(0)
const collectCurrentArea = ref(1)
const collectTotalTrash = ref(0)
const collectTimers = ref<ReturnType<typeof setTimeout>[]>([])
const collectReportTimer = ref<ReturnType<typeof setInterval> | null>(null)
const collectLogRef = ref<HTMLElement | null>(null)

function pushCollectLog(text: string) {
  collectLogs.value.push(text)
  nextTick(() => scrollLogToBottom(collectLogRef.value))
}

function clearCollectTimers() {
  collectTimers.value.forEach(t => clearTimeout(t))
  collectTimers.value = []
  if (collectReportTimer.value !== null) {
    clearInterval(collectReportTimer.value)
    collectReportTimer.value = null
  }
}

function resetCollectState() {
  clearCollectTimers()
  collectPhase.value = 'idle'
  collectLogs.value = []
  collectProgress.value = 0
  collectCurrentArea.value = 1
  collectTotalTrash.value = 0
}

/** 启动单个区域的扫描 */
function startArea(area: number) {
  collectCurrentArea.value = area
  collectProgress.value = Math.round(((area - 1) / TOTAL_AREAS) * 100)

  // 推送区域扫描开始日志
  pushCollectLog(`正在扫描区域${area}/${TOTAL_AREAS}....`)

  // 在本区域内随机 0-5 个时间点发现垃圾
  const trashCount = Math.floor(Math.random() * 6) // 0-5
  const trashTimePoints: number[] = []
  for (let i = 0; i < trashCount; i++) {
    trashTimePoints.push(Math.random() * (AREA_DURATION_MS - 5000)) // 0-55s 内
  }
  trashTimePoints.sort((a, b) => a - b)

  // 为每个垃圾发现设置定时器
  trashTimePoints.forEach((tp) => {
    const timer = setTimeout(() => {
      if (collectPhase.value !== 'running') return
      collectTotalTrash.value++
      pushCollectLog(`累计清理垃圾: ${collectTotalTrash.value}`)
    }, tp)
    collectTimers.value.push(timer)
  })

  // 区域结束时推进到下一个区域
  const areaTimer = setTimeout(() => {
    if (collectPhase.value !== 'running') return
    if (area >= TOTAL_AREAS) {
      // 所有区域完成
      collectPhase.value = 'completed'
      collectProgress.value = 100
      pushCollectLog(`任务完成，共清理垃圾: ${collectTotalTrash.value}`)
      if (collectReportTimer.value !== null) {
        clearInterval(collectReportTimer.value)
        collectReportTimer.value = null
      }
    } else {
      startArea(area + 1)
    }
  }, AREA_DURATION_MS)
  collectTimers.value.push(areaTimer)
}

/** 5s 循环播报 */
function startCollectReport() {
  if (collectReportTimer.value !== null) return
  collectReportTimer.value = setInterval(() => {
    if (collectPhase.value !== 'running') return
    pushCollectLog(`正在扫描区域${collectCurrentArea.value}/${TOTAL_AREAS}....累计清理垃圾: ${collectTotalTrash.value}`)
  }, REPORT_INTERVAL_MS)
}

async function onCollectStart() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    robots.applyRobot(await postModeCommand(robot.id, '自动'))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '垃圾收集任务启动失败')
    return
  }
  resetCollectState()
  collectPhase.value = 'running'
  pushCollectLog('开始执行任务')

  logs.append('操作', robot.id, '开始垃圾收集任务')

  startArea(1)
  startCollectReport()
}

async function onCollectPause() {
  if (!ensureCanControl()) return
  try {
    robots.applyRobot(await postNavigationPause(r.value!.id))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '暂停垃圾收集任务失败')
    return
  }
  collectPhase.value = 'paused'
  clearCollectTimers()
  pushCollectLog('任务已暂停')
  logs.append('操作', r.value!.id, '暂停垃圾收集任务')
}

async function onCollectStop() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    robots.applyRobot(await postNavigationStop(robot.id))
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '停止垃圾收集任务失败')
    return
  }
  resetCollectState()
  logs.append('操作', robot.id, '停止垃圾收集任务')
}

// ─── 导航任务操作 ───

async function onSendGoal() {
  if (!ensureCanControl()) return
  const robot = r.value!
  const goalPoint = { id: crypto.randomUUID(), lat: goal.value.lat, lon: goal.value.lon, speed: goal.value.speed }
  logs.append('操作', robot.id, `下发目标点 (${goal.value.lat.toFixed(5)}, ${goal.value.lon.toFixed(5)}) 速度 ${goal.value.speed} m/s`)
  try {
    const updated = await postNavigationStart(robot.id, [goalPoint])
    robots.applyRobot(updated)
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端目标点任务下发失败')
  }
}
async function onStart() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    const updated = await postNavigationResume(robot.id)
    robots.applyRobot(updated)
    logs.append('操作', robot.id, '开始任务')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端开始任务失败')
  }
}
async function onPause() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    const updated = await postNavigationPause(robot.id)
    robots.applyRobot(updated)
    logs.append('操作', robot.id, '暂停任务')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端暂停任务失败')
  }
}
async function onStop() {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    const updated = await postNavigationStop(robot.id)
    robots.applyRobot(updated)
    logs.append('操作', robot.id, '停止任务')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端停止任务失败')
  }
}

function addWaypoint() {
  const last = route.value.waypoints[route.value.waypoints.length - 1]
  const idx = (last?.index ?? 0) + 1
  route.value.waypoints.push({
    index: idx,
    lat: (last?.lat ?? 30.2755) + 0.0008,
    lon: (last?.lon ?? 120.157) + 0.0008,
    speed: route.value.cruiseSpeed
  })
}
function removeWaypoint(i: number) {
  route.value.waypoints.splice(i, 1)
}
async function onSendRoute() {
  if (!ensureCanControl()) return
  const robot = r.value!
  const goalPoints = route.value.waypoints.map(wp => ({
    id: crypto.randomUUID(),
    lat: wp.lat,
    lon: wp.lon,
    speed: wp.speed > 0 ? wp.speed : route.value.cruiseSpeed
  }))
  logs.append(
    '操作',
    robot.id,
    `下发路线任务,共 ${route.value.waypoints.length} 个航点,巡航 ${route.value.cruiseSpeed} m/s${route.value.loop ? ',循环' : ''}`
  )
  try {
    const updated = await postNavigationStart(robot.id, goalPoints)
    robots.applyRobot(updated)
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端路线任务下发失败')
  }
}

async function onToggleRelay() {
  const robot = r.value
  if (!robot || !canToggleRelay.value || robot.relayEnabled === null) return
  const enabled = !robot.relayEnabled
  relayChanging.value = true
  try {
    const updated = await postElectromagneticFix(robot.id, enabled)
    robots.applyRobot(updated)
    ElMessage.success(`电磁固定已${enabled ? '开启' : '关闭'}`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '电磁固定切换失败')
  } finally {
    relayChanging.value = false
  }
}

function clearWirelessChargingCheck() {
  if (wirelessChargeTimer !== null) {
    clearTimeout(wirelessChargeTimer)
    wirelessChargeTimer = null
  }
  wirelessChargingChecking.value = false
}

function onWirelessChargingToggle() {
  if (!isClUsv.value || !ensureCanControl() || wirelessChargingChecking.value) return
  const robotId = r.value!.id
  wirelessChargingChecking.value = true
  wirelessChargeTimer = setTimeout(() => {
    wirelessChargeTimer = null
    wirelessChargingChecking.value = false
    if (r.value?.id !== robotId) return
    ElMessage.error('检测无负载，禁止开启')
    logs.append('操作', robotId, '无线充电开启失败：检测无负载，禁止开启')
  }, 500)
}

async function onAction(name: string) {
  if (!ensureCanControl()) return
  const robot = r.value!
  try {
    let updated: Robot | null = null
    if (name === '返航') updated = await postNavigationReturnHome(robot.id)
    else if (name === '原地停止' || name === '复位设备') updated = await postNavigationStop(robot.id)
    else {
      ElMessage.info(`${name} 的设备协议尚未接入`)
      return
    }
    robots.applyRobot(updated)
    logs.append('操作', robot.id, `执行简单动作:${name}`)
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端简单动作执行失败')
  }
}

function formatNum(v: number | null, unit: string, digits: number) {
  if (v == null) return '--'
  return `${v.toFixed(digits)} ${unit}`
}
function formatPos(p: { lat: number; lon: number } | null) {
  if (!p) return '未知'
  return `${p.lat.toFixed(5)}, ${p.lon.toFixed(5)}`
}

// ─── 清理 ───

onUnmounted(() => {
  clearChargingTimers()
  clearCollectTimers()
  clearWirelessChargingCheck()
})

// 切换设备时重置所有任务状态
watch(() => robots.selectedId, () => {
  resetChargingState()
  resetCollectState()
  clearWirelessChargingCheck()
})

// Local demo timers must never outlive the connection that authorized them.
watch(canControl, enabled => {
  if (!enabled) {
    resetChargingState()
    resetCollectState()
    clearWirelessChargingCheck()
  }
})
</script>

<style scoped>
.mission {
  height: 100%;
}
.mission-grid {
  display: grid;
  grid-template-columns: 220px 1fr 280px;
  gap: 12px;
  height: 100%;
}
.panel {
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: auto;
}

.task-types {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.task-type {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  background: var(--bg-panel-2);
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}
.task-type:hover {
  border-color: var(--border-strong);
}
.task-type.active {
  background: rgba(59, 130, 246, 0.1);
  border-color: var(--color-accent);
}
.task-type :deep(.el-icon) {
  font-size: 20px;
  color: var(--color-accent);
}
.task-type .name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-1);
}
.task-type .desc {
  font-size: 11.5px;
  color: var(--text-3);
}

.form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.action-row {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}
.action-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  max-width: 480px;
}
.action-grid :deep(.simple-action-button) {
  width: 100%;
  margin-left: 0;
}

.charging-desc {
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 8px;
}

.status .progress-block {
  margin-top: 12px;
  border-top: 1px dashed var(--border);
  padding-top: 12px;
}
.status .progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-3);
  margin-bottom: 6px;
}

/* 滚动日志（充电 & 垃圾收集共用） */
.scroll-log {
  margin-top: 14px;
  border-top: 1px dashed var(--border);
  padding-top: 10px;
  height: 160px;
  overflow-y: auto;
  font-family: 'Cascadia Code', 'Fira Code', 'Consolas', monospace;
  font-size: 11.5px;
  line-height: 1.7;
  color: var(--text-2);
  background: var(--bg-panel-2);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 10px;
}
.scroll-log .log-line {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.scroll-log .log-line::before {
  content: '›';
  margin-right: 6px;
  color: var(--color-accent);
  font-weight: bold;
}

.hint {
  margin-top: 14px;
}
.small {
  font-size: 11.5px;
}
</style>
