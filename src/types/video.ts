export const CAMERA_SLOT_COUNT = 4

export type CameraSlotIndex = 0 | 1 | 2 | 3

export type CameraTileStatus =
  | 'unsupported'
  | 'permission_required'
  | 'idle'
  | 'connecting'
  | 'streaming'
  | 'error'

export interface CameraDeviceInfo {
  deviceId: string
  groupId: string
  label: string
}
