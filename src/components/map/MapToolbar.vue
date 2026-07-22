<template>
  <div class="map-toolbar">
    <div class="toolbar-left">
      <el-button-group>
        <el-button
          ref="addGoalBtnRef"
          :icon="pickingMode ? Close : Plus"
          :type="pickingMode ? 'warning' : 'default'"
          @click="onTogglePick"
        >
          {{ pickingMode ? '取消选点' : '添加目标点' }}
        </el-button>
        <el-button :icon="Promotion" :disabled="!hasGoal || !canControl" @click="$emit('send-goal')">下发目标点</el-button>
        <el-button :icon="Delete" :disabled="!hasGoal" @click="$emit('clear-goals')">清除目标点</el-button>
        <el-button :icon="VideoPlay" type="primary" :disabled="!canControl" @click="$emit('start')">开始导航</el-button>
        <el-button :icon="VideoPause" :disabled="!canControl" @click="$emit('pause')">暂停</el-button>
        <el-button :icon="CircleClose" :disabled="!canControl" @click="$emit('stop')">停止</el-button>
        <el-button :icon="Back" :disabled="!canControl" @click="$emit('return')">返航</el-button>
        <el-button :icon="Brush" @click="$emit('clear-trail')">清除轨迹</el-button>
      </el-button-group>
    </div>
    <div class="toolbar-right">
      <el-radio-group :model-value="baseMap" size="small" @change="onBaseMapChange">
        <el-radio-button value="satellite">卫星</el-radio-button>
        <el-radio-button value="normal">平面</el-radio-button>
      </el-radio-group>
      <span class="switch-label">路网</span>
      <el-switch
        :model-value="effectiveRoadNet"
        :disabled="baseMap === 'normal'"
        @change="onRoadNetChange"
      />
      <div class="hint muted">{{ hintText }}</div>
    </div>

    <!-- 虚拟触发下拉菜单：hover 时在"添加目标点"按钮下方弹出 -->
    <el-dropdown
      trigger="hover"
      virtual-triggering
      :virtual-ref="addGoalBtnRef"
      @command="onDropdownCommand"
    >
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item command="input-coords">输入坐标</el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  Plus,
  Close,
  Promotion,
  VideoPlay,
  VideoPause,
  CircleClose,
  Back,
  Brush,
  Delete
} from '@element-plus/icons-vue'

interface Props {
  hasGoal: boolean
  goalCount: number
  canControl: boolean
  baseMap: 'satellite' | 'normal'
  showRoadNet: boolean
  pickingMode: boolean
}
const props = defineProps<Props>()

/** "添加目标点"按钮的 ref，供虚拟触发下拉菜单使用 */
const addGoalBtnRef = ref<HTMLElement | null>(null)

const emit = defineEmits<{
  (e: 'add-goal'): void
  (e: 'send-goal'): void
  (e: 'clear-goals'): void
  (e: 'start'): void
  (e: 'pause'): void
  (e: 'stop'): void
  (e: 'return'): void
  (e: 'clear-trail'): void
  (e: 'switch-base-map', baseMap: string): void
  (e: 'toggle-road-net', show: boolean): void
  (e: 'enter-pick-mode'): void
  (e: 'cancel-pick-mode'): void
  (e: 'input-coords'): void
}>()

const effectiveRoadNet = computed(() => props.baseMap === 'normal' ? true : props.showRoadNet)

const hintText = computed(() => {
  if (props.pickingMode) return '请在地图上点击选择目标点位置'
  if (!props.canControl) return '当前设备离线,无法控制'
  if (!props.hasGoal) return '点击"添加目标点"在地图上选点,或下拉输入坐标'
  return `已设置 ${props.goalCount} 个目标点,可下发并开始导航`
})

function onTogglePick() {
  if (props.pickingMode) {
    emit('cancel-pick-mode')
  } else {
    emit('enter-pick-mode')
  }
}

function onDropdownCommand(cmd: string) {
  if (cmd === 'input-coords') {
    emit('input-coords')
  }
}

function onBaseMapChange(val: string | number | boolean) {
  emit('switch-base-map', val as 'satellite' | 'normal')
}

function onRoadNetChange(val: string | number | boolean) {
  emit('toggle-road-net', !!val)
}
</script>

<style scoped>
.map-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 8px 12px;
  gap: 12px;
}
.toolbar-left {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
.switch-label {
  font-size: 13px;
  color: var(--text-2);
  white-space: nowrap;
}
.hint {
  font-size: 12px;
  white-space: nowrap;
}
</style>
