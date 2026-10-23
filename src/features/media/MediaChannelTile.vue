<template>
  <article class="tile" :class="{ active: Boolean(stream) }">
    <div class="viewport">
      <video ref="video" autoplay muted playsinline />
      <div v-if="!stream" class="placeholder">
        <el-icon><VideoCamera /></el-icon>
        <span>{{
          error ||
          (!online
            ? '设备离线，媒体轨道已释放'
            : selectedDeviceId
              ? '等待打开本机 UVC'
              : '尚未绑定本机摄像头')
        }}</span>
      </div>
    </div>
    <div class="camera-top">
      <span class="channel-label">{{ displayName }}</span>
      <StatusBadge :label="statusLabel" :tone="statusTone" />
    </div>
    <div class="controls">
      <el-select
        v-model="selectedDeviceId"
        size="small"
        placeholder="选择本机 UVC"
        @visible-change="onSelectVisible"
      >
        <el-option
          v-for="device in cameras"
          :key="device.deviceId"
          :label="device.label || '未命名摄像头'"
          :value="device.deviceId"
        />
      </el-select>
      <el-button
        size="small"
        :disabled="!online || !selectedDeviceId"
        :loading="opening"
        @click="open"
        >打开</el-button
      >
      <el-button size="small" :disabled="!stream" @click="close">关闭</el-button>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { VideoCamera } from '@element-plus/icons-vue'
import { bindingKey, readBinding, writeBinding } from '@/shared/media/bindings'
import { LocalUvcSource, mediaErrorMessage } from '@/shared/media/source'
import StatusBadge from '@/shared/ui/StatusBadge.vue'

const props = defineProps<{
  deviceId: string
  channelId: string
  displayName: string
  online: boolean
}>()
const video = ref<HTMLVideoElement | null>(null)
const cameras = ref<MediaDeviceInfo[]>([])
const selectedDeviceId = ref('')
const stream = ref<MediaStream | null>(null)
const opening = ref(false)
const error = ref<string | null>(null)
let source: LocalUvcSource | null = null
let openGeneration = 0

const statusLabel = computed(() =>
  stream.value ? 'UVC 已打开' : error.value ? '媒体错误' : props.online ? '待打开' : '已释放'
)
const statusTone = computed(() =>
  stream.value ? 'success' : error.value ? 'danger' : props.online ? 'warning' : 'neutral'
)

onMounted(loadBinding)

watch(
  () => props.online,
  async (online) => {
    if (!online) close()
    else if (selectedDeviceId.value) await open()
  }
)

watch(() => [props.deviceId, props.channelId], loadBinding)
onBeforeUnmount(close)

async function enumerate() {
  if (!navigator.mediaDevices?.enumerateDevices) {
    error.value = '当前浏览器不支持 MediaDevices'
    return
  }
  cameras.value = (await navigator.mediaDevices.enumerateDevices()).filter(
    (item) => item.kind === 'videoinput'
  )
}

async function loadBinding() {
  close()
  selectedDeviceId.value = ''
  const key = bindingKey(props.deviceId, props.channelId)
  const saved = await readBinding(key).catch(() => null)
  if (key !== bindingKey(props.deviceId, props.channelId)) return
  if (saved) selectedDeviceId.value = saved.browserDeviceId
  if (props.online && selectedDeviceId.value) await open()
}

async function onSelectVisible(visible: boolean) {
  if (!visible) return
  try {
    await enumerate()
    if (!cameras.value.length) {
      const permission = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      permission.getTracks().forEach((track) => track.stop())
      await enumerate()
    }
  } catch (reason) {
    error.value = mediaErrorMessage(reason)
  }
}

async function open() {
  if (!props.online || !selectedDeviceId.value || opening.value) return
  close()
  const generation = ++openGeneration
  opening.value = true
  error.value = null
  const candidate = new LocalUvcSource(selectedDeviceId.value)
  try {
    const opened = await candidate.start()
    if (generation !== openGeneration || !props.online) {
      candidate.stop()
      return
    }
    source = candidate
    stream.value = opened
    await nextTick()
    if (video.value) video.value.srcObject = stream.value
    const selected = cameras.value.find((item) => item.deviceId === selectedDeviceId.value)
    await writeBinding({
      key: bindingKey(props.deviceId, props.channelId),
      browserDeviceId: selectedDeviceId.value,
      label: selected?.label ?? ''
    })
  } catch (reason) {
    if (generation === openGeneration) {
      const message = mediaErrorMessage(reason)
      error.value = message || null
      close(false)
      opening.value = false
    }
  } finally {
    if (generation === openGeneration) opening.value = false
  }
}

function close(clearError = true) {
  openGeneration += 1
  source?.stop()
  source = null
  stream.value = null
  if (video.value) video.value.srcObject = null
  if (clearError) error.value = null
}
</script>

<style scoped>
.tile {
  position: relative;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  border: 1px solid var(--border);
  background: #020617;
  overflow: hidden;
}

.viewport {
  position: absolute;
  inset: 0;
  background: #020609;
}

video {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: #000;
}

.placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 60px 20px 72px;
  color: #8794aa;
  text-align: center;
  font-size: 11.5px;
}

.placeholder .el-icon {
  font-size: 34px;
}

.camera-top {
  position: absolute;
  inset: 6px 6px auto;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  pointer-events: none;
}

.channel-label {
  display: inline-flex;
  min-height: 22px;
  align-items: center;
  padding: 2px 7px;
  color: #e5e7eb;
  border-radius: 4px;
  background: rgb(0 0 0 / 56%);
  font-size: 11px;
  font-weight: 700;
}

.controls {
  position: absolute;
  right: 8px;
  bottom: 8px;
  left: 8px;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 6px;
  padding: 7px;
  border: 1px solid rgb(148 163 184 / 28%);
  border-radius: 6px;
  background: rgb(15 23 42 / 82%);
  backdrop-filter: blur(6px);
}
</style>
