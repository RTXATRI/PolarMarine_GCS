<template>
  <div class="camera-tile" :class="{ active: status === 'streaming' }">
    <video ref="videoRef" class="camera-video" autoplay muted playsinline />

    <div v-if="status !== 'streaming'" class="camera-empty">
      <el-icon><VideoCamera /></el-icon>
      <span>{{ statusText }}</span>
      <span v-if="detailText" class="detail">{{ detailText }}</span>
    </div>

    <div class="camera-top">
      <span class="cam-label">{{ label }}</span>
      <span class="cam-status" :class="status">{{ statusText }}</span>
    </div>

    <div class="camera-controls">
      <el-select
        :model-value="selectedDeviceId"
        filterable
        clearable
        placeholder="选择摄像头"
        size="small"
        class="device-select"
        @change="onDeviceChange"
        @clear="onClearDevice"
      >
        <el-option
          v-for="device in videoStore.devices"
          :key="device.deviceId"
          :label="device.label"
          :value="device.deviceId"
        />
      </el-select>
      <el-button size="small" :icon="Refresh" @click="onAuthorizeAndRefresh">
        授权/刷新
      </el-button>
      <el-button size="small" :icon="VideoPause" :disabled="!stream" @click="stopStream">
        停止
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, VideoCamera, VideoPause } from '@element-plus/icons-vue'
import { useVideoStore } from '@/stores/video'
import { openVideoStream } from '@/utils/media-devices'
import type { CameraSlotIndex, CameraTileStatus } from '@/types/video'

const props = defineProps<{
  robotId: string
  slotIndex: CameraSlotIndex
  label: string
}>()

const videoStore = useVideoStore()
const videoRef = ref<HTMLVideoElement | null>(null)
const selectedDeviceId = ref<string | null>(null)
const status = ref<CameraTileStatus>('idle')
const detailText = ref('')
const stream = ref<MediaStream | null>(null)
let mounted = false
let streamGeneration = 0

const statusText = computed(() => {
  if (status.value === 'unsupported') return '不支持摄像头'
  if (status.value === 'permission_required') return '未授权'
  if (status.value === 'connecting') return '连接中'
  if (status.value === 'streaming') return '显示中'
  if (status.value === 'error') return '设备不可用'
  return '未选择'
})

function loadSelection() {
  selectedDeviceId.value = videoStore.getSelectedDeviceId(props.robotId, props.slotIndex)
}

async function onAuthorizeAndRefresh() {
  try {
    await videoStore.requestPermissionAndRefresh()
    if (!mounted) return
    if (selectedDeviceId.value) {
      await startStream(selectedDeviceId.value)
    } else {
      status.value = 'idle'
      detailText.value = videoStore.devices.length ? '请选择一个视频输入设备' : '未发现视频输入设备'
    }
  } catch (error) {
    status.value = 'permission_required'
    detailText.value = error instanceof Error ? error.message : '摄像头权限被拒绝'
  }
}

async function onDeviceChange(value: string | number | boolean | undefined) {
  const deviceId = typeof value === 'string' ? value : null
  selectedDeviceId.value = deviceId
  videoStore.setSelectedDeviceId(props.robotId, props.slotIndex, deviceId)

  if (!deviceId) {
    stopStream()
    status.value = 'idle'
    detailText.value = '请选择一个视频输入设备'
    return
  }

  await startStream(deviceId)
}

function onClearDevice() {
  selectedDeviceId.value = null
  videoStore.setSelectedDeviceId(props.robotId, props.slotIndex, null)
  stopStream()
  status.value = 'idle'
  detailText.value = '请选择一个视频输入设备'
}

async function startStream(deviceId: string) {
  stopStream()
  const generation = streamGeneration

  if (!videoStore.supported) {
    status.value = 'unsupported'
    detailText.value = '请使用支持 MediaDevices 的浏览器'
    return
  }

  status.value = 'connecting'
  detailText.value = ''

  try {
    const nextStream = await openVideoStream(deviceId)
    if (!mounted || generation !== streamGeneration) {
      nextStream.getTracks().forEach(track => track.stop())
      return
    }
    stream.value = nextStream
    await nextTick()
    if (!mounted || generation !== streamGeneration || !videoRef.value) {
      nextStream.getTracks().forEach(track => track.stop())
      if (stream.value === nextStream) stream.value = null
      return
    }
    videoRef.value.srcObject = nextStream
    await videoRef.value.play()
    if (!mounted || generation !== streamGeneration) {
      nextStream.getTracks().forEach(track => track.stop())
      if (stream.value === nextStream) stream.value = null
      return
    }
    status.value = 'streaming'
    detailText.value = ''
  } catch (error) {
    if (!mounted || generation !== streamGeneration) return
    stopStream()
    status.value = 'error'
    detailText.value = error instanceof Error ? error.message : '摄像头被占用或无法打开'
    ElMessage.error(`${props.label} 摄像头打开失败`)
  }
}

function stopStream() {
  streamGeneration += 1
  if (videoRef.value) {
    videoRef.value.srcObject = null
  }
  stream.value?.getTracks().forEach(track => track.stop())
  stream.value = null
  if (status.value === 'streaming' || status.value === 'connecting') {
    status.value = selectedDeviceId.value ? 'idle' : 'idle'
  }
}

onMounted(async () => {
  mounted = true
  loadSelection()
  await videoStore.refreshDevices()
  if (!mounted) return
  if (!videoStore.supported) {
    status.value = 'unsupported'
    detailText.value = '请使用 localhost/127.0.0.1 或 HTTPS 访问'
    return
  }
  if (selectedDeviceId.value) {
    await startStream(selectedDeviceId.value)
  } else {
    status.value = 'permission_required'
    detailText.value = '点击授权/刷新后选择摄像头'
  }
})

watch(
  () => props.robotId,
  async () => {
    stopStream()
    loadSelection()
    if (selectedDeviceId.value) {
      await startStream(selectedDeviceId.value)
    } else {
      status.value = 'permission_required'
      detailText.value = '点击授权/刷新后选择摄像头'
    }
  }
)

onBeforeUnmount(() => {
  mounted = false
  stopStream()
})
</script>

<style scoped>
.camera-tile {
  position: relative;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  background: #020617;
  border: 1px solid var(--border);
}

.camera-video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.camera-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 56px 18px 70px;
  color: var(--text-3);
  text-align: center;
  pointer-events: none;
}

.camera-empty .el-icon {
  font-size: 34px;
}

.detail {
  max-width: 80%;
  font-size: 11.5px;
  line-height: 1.5;
}

.camera-top {
  position: absolute;
  top: 6px;
  left: 6px;
  right: 6px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  pointer-events: none;
}

.cam-label,
.cam-status {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 2px 7px;
  border-radius: 4px;
  color: #e5e7eb;
  background: rgba(0, 0, 0, 0.52);
  font-size: 11px;
  font-weight: 700;
}

.cam-status.streaming {
  color: #bbf7d0;
}

.cam-status.error,
.cam-status.unsupported {
  color: #fecaca;
}

.cam-status.permission_required {
  color: #fde68a;
}

.camera-controls {
  position: absolute;
  left: 8px;
  right: 8px;
  bottom: 8px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 6px;
  padding: 7px;
  border: 1px solid rgba(148, 163, 184, 0.28);
  border-radius: 6px;
  background: rgba(15, 23, 42, 0.82);
  backdrop-filter: blur(6px);
}

.device-select {
  min-width: 0;
}
</style>
