import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

export type SystemHealth = '系统正常' | '部分异常' | '严重异常'
export type BackendState = 'connecting' | 'connected' | 'disconnected'

export const useSystemStore = defineStore('system', () => {
  const startedAt = ref<string>(new Date().toISOString())
  const now = ref<number>(Date.now())
  const backendState = ref<BackendState>('connecting')
  const backendError = ref<string | null>(null)
  const lastBackendConnectedAt = ref<string | null>(null)

  let timer: number | null = null

  function startClock() {
    if (timer !== null) return
    timer = window.setInterval(() => {
      now.value = Date.now()
    }, 1000)
  }

  function stopClock() {
    if (timer !== null) {
      window.clearInterval(timer)
      timer = null
    }
  }

  const nowText = computed(() => {
    const d = new Date(now.value)
    const pad = (n: number) => n.toString().padStart(2, '0')
    return (
      d.getFullYear() +
      '-' +
      pad(d.getMonth() + 1) +
      '-' +
      pad(d.getDate()) +
      ' ' +
      pad(d.getHours()) +
      ':' +
      pad(d.getMinutes()) +
      ':' +
      pad(d.getSeconds())
    )
  })

  const backendConnected = computed(() => backendState.value === 'connected')

  function setBackendState(state: BackendState, error: string | null = null) {
    backendState.value = state
    backendError.value = error
    if (state === 'connected') lastBackendConnectedAt.value = new Date().toISOString()
  }

  return {
    startedAt,
    now,
    nowText,
    backendState,
    backendError,
    backendConnected,
    lastBackendConnectedAt,
    setBackendState,
    startClock,
    stopClock
  }
})
