import { ref } from 'vue'
import { defineStore } from 'pinia'
import type { Bootstrap } from '@/entities/types'

export const useApplicationStore = defineStore('application', () => {
  const streamState = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const lastError = ref<string | null>(null)
  const settings = ref<Bootstrap['settings']>({
    baiduMapAk: null,
    offlineMapStyleUrl: null,
    simulatorLabel: '仿真数据',
    maxConfiguredDevices: 50,
    maxOnlineDevices: 20
  })

  function setStreamState(state: typeof streamState.value, error?: string) {
    streamState.value = state
    lastError.value = error ?? null
  }

  return { streamState, lastError, settings, setStreamState }
})
