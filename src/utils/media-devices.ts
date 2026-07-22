import type { CameraDeviceInfo } from '@/types/video'

export function supportsCameraDevices(): boolean {
  return !!navigator.mediaDevices?.getUserMedia && !!navigator.mediaDevices?.enumerateDevices
}

export async function requestCameraPermission(): Promise<void> {
  if (!supportsCameraDevices()) {
    throw new Error('当前浏览器不支持摄像头访问')
  }

  const stream = await navigator.mediaDevices.getUserMedia({
    video: true,
    audio: false
  })
  stream.getTracks().forEach(track => track.stop())
}

export async function listVideoInputDevices(): Promise<CameraDeviceInfo[]> {
  if (!supportsCameraDevices()) {
    return []
  }

  const devices = await navigator.mediaDevices.enumerateDevices()
  return devices
    .filter(device => device.kind === 'videoinput')
    .map((device, index) => ({
      deviceId: device.deviceId,
      groupId: device.groupId,
      label: device.label || `摄像头 ${index + 1}`
    }))
}

export async function openVideoStream(deviceId: string): Promise<MediaStream> {
  if (!supportsCameraDevices()) {
    throw new Error('当前浏览器不支持摄像头访问')
  }

  return navigator.mediaDevices.getUserMedia({
    video: {
      deviceId: { exact: deviceId }
    },
    audio: false
  })
}
