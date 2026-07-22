<template>
  <div class="camera-grid">
    <CameraTile
      v-for="slot in slots"
      :key="`${robotId}-${slot}`"
      :robot-id="robotId"
      :slot-index="slot"
      :label="cameraLabels[slot]"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted } from 'vue'
import CameraTile from '@/components/video/CameraTile.vue'
import { useVideoStore } from '@/stores/video'
import type { CameraSlotIndex } from '@/types/video'

defineProps<{
  robotId: string
}>()

const videoStore = useVideoStore()
const slots: CameraSlotIndex[] = [0, 1, 2, 3]
const cameraLabels = ['CAM-1', 'CAM-2', 'CAM-3', 'CAM-4'] as const

async function refreshDevices() {
  await videoStore.refreshDevices()
}

onMounted(() => {
  void refreshDevices()
  navigator.mediaDevices?.addEventListener?.('devicechange', refreshDevices)
})

onBeforeUnmount(() => {
  navigator.mediaDevices?.removeEventListener?.('devicechange', refreshDevices)
})
</script>

<style scoped>
.camera-grid {
  display: grid;
  width: 100%;
  height: 100%;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  background: #020617;
}
</style>
