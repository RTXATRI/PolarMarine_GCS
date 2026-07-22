import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { listVideoInputDevices, requestCameraPermission, supportsCameraDevices } from '@/utils/media-devices'
import type { CameraDeviceInfo, CameraSlotIndex } from '@/types/video'

function selectionKey(robotId: string, slotIndex: number): string {
  return `gcs.camera.${robotId}.${slotIndex}`
}

export const useVideoStore = defineStore('video', () => {
  const devices = ref<CameraDeviceInfo[]>([])
  const permissionGranted = ref(false)
  const lastError = ref<string | null>(null)
  const selectedDeviceIds = ref<Record<string, string | null>>({})

  const supported = computed(() => supportsCameraDevices())

  function getSelectedDeviceId(robotId: string, slotIndex: CameraSlotIndex): string | null {
    const key = selectionKey(robotId, slotIndex)
    if (!(key in selectedDeviceIds.value)) {
      selectedDeviceIds.value[key] = localStorage.getItem(key)
    }
    return selectedDeviceIds.value[key] || null
  }

  function setSelectedDeviceId(robotId: string, slotIndex: CameraSlotIndex, deviceId: string | null) {
    const key = selectionKey(robotId, slotIndex)
    selectedDeviceIds.value[key] = deviceId
    if (deviceId) {
      localStorage.setItem(key, deviceId)
    } else {
      localStorage.removeItem(key)
    }
  }

  async function refreshDevices() {
    if (!supported.value) {
      devices.value = []
      lastError.value = '当前浏览器不支持摄像头访问'
      return
    }

    try {
      devices.value = await listVideoInputDevices()
      lastError.value = null
    } catch (error) {
      lastError.value = error instanceof Error ? error.message : '摄像头设备枚举失败'
      devices.value = []
    }
  }

  async function requestPermissionAndRefresh() {
    if (!supported.value) {
      lastError.value = '当前浏览器不支持摄像头访问'
      return
    }

    try {
      await requestCameraPermission()
      permissionGranted.value = true
      await refreshDevices()
    } catch (error) {
      permissionGranted.value = false
      lastError.value = error instanceof Error ? error.message : '摄像头权限被拒绝'
      throw error
    }
  }

  return {
    devices,
    supported,
    permissionGranted,
    lastError,
    getSelectedDeviceId,
    setSelectedDeviceId,
    refreshDevices,
    requestPermissionAndRefresh
  }
})
