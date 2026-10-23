<template>
  <div class="map-viewport">
    <div ref="container" class="map-container" :class="{ picking }" />
    <div v-if="loading" class="overlay">正在初始化地图引擎…</div>
    <div v-else-if="error" class="overlay error">{{ error }}</div>
    <StatusBadge
      v-if="providerName"
      class="provider"
      :label="providerName"
      :tone="providerName.includes('离线') ? 'warning' : 'info'"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useApplicationStore } from '@/app/store'
import { BaiduMapProvider } from '@/shared/map/baidu-provider'
import { MapLibreProvider } from '@/shared/map/maplibre-provider'
import type {
  MapOverlay,
  MapProvider,
  MapProviderCapabilities,
  Wgs84Coordinate
} from '@/shared/map/types'
import StatusBadge from '@/shared/ui/StatusBadge.vue'

const props = withDefaults(defineProps<{ overlays: MapOverlay[]; picking?: boolean }>(), {
  picking: false
})
const emit = defineEmits<{
  pointPicked: [coordinate: Wgs84Coordinate]
  providerReady: [capabilities: MapProviderCapabilities]
}>()
const application = useApplicationStore()
const container = ref<HTMLElement | null>(null)
const loading = ref(false)
const error = ref<string | null>(null)
const providerName = ref('')
let provider: MapProvider | null = null
let generation = 0

watch(
  () => [application.settings.baiduMapAk, application.settings.offlineMapStyleUrl],
  () => {
    void initialize()
  }
)
watch(
  () => props.picking,
  (picking) => configurePicking(picking)
)
watch(
  () => props.overlays,
  (overlays) => provider?.setOverlays(overlays),
  { deep: true }
)
onMounted(() => {
  window.addEventListener('online', initialize)
  window.addEventListener('offline', initialize)
  void initialize()
})
onBeforeUnmount(() => {
  generation += 1
  provider?.destroy()
  window.removeEventListener('online', initialize)
  window.removeEventListener('offline', initialize)
})

async function initialize() {
  if (!container.value) return
  const currentGeneration = ++generation
  provider?.destroy()
  provider = null
  container.value.replaceChildren()
  loading.value = true
  error.value = null
  providerName.value = ''
  const candidates: MapProvider[] = []
  if (navigator.onLine && application.settings.baiduMapAk)
    candidates.push(new BaiduMapProvider(application.settings.baiduMapAk))
  if (application.settings.offlineMapStyleUrl)
    candidates.push(new MapLibreProvider(application.settings.offlineMapStyleUrl))
  for (const candidate of candidates) {
    try {
      await candidate.mount(container.value)
      if (currentGeneration !== generation) {
        candidate.destroy()
        return
      }
      provider = candidate
      providerName.value = candidate.name
      provider.setOverlays(props.overlays)
      configurePicking(props.picking)
      emit('providerReady', candidate.capabilities)
      loading.value = false
      return
    } catch (reason) {
      candidate.destroy()
      console.error('Map provider failed', reason)
    }
  }
  if (currentGeneration === generation) {
    loading.value = false
    error.value = candidates.length
      ? '在线与离线地图引擎均不可用；设备坐标仍按 WGS-84 保留。'
      : '尚未在本机配置百度地图 AK 或离线地图样式。'
  }
}

function configurePicking(enabled: boolean): void {
  provider?.setPointPickHandler(enabled ? (coordinate) => emit('pointPicked', coordinate) : null)
}
</script>

<style scoped>
.map-viewport {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 480px;
  overflow: hidden;
  background: #050a0f;
}

.map-container {
  width: 100%;
  height: 100%;
}

.map-container.picking {
  cursor: crosshair;
}

.overlay {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  padding: 24px;
  color: var(--text-3);
  text-align: center;
  background: radial-gradient(circle at center, rgb(17 34 51 / 60%), #050a0f);
}

.overlay.error {
  color: var(--color-warn);
}

.provider {
  position: absolute;
  top: 10px;
  left: 10px;
  z-index: 4;
}
</style>
