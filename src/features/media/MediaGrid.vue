<template>
  <section
    class="media-grid"
    :class="{
      single: channels.length === 1,
      double: channels.length === 2,
      quad: channels.length >= 3 && channels.length <= 4,
      scrolling: channels.length > 4
    }"
  >
    <MediaChannelTile
      v-for="channel in channels"
      :key="deviceId + ':' + channel.id"
      :device-id="deviceId"
      :channel-id="channel.id"
      :display-name="channel.displayName"
      :online="online"
    />
    <p v-if="!channels.length" class="empty">当前设备模板未声明媒体通道。</p>
  </section>
</template>

<script setup lang="ts">
import type { DeviceTemplate } from '@/entities/types'
import MediaChannelTile from '@/features/media/MediaChannelTile.vue'

type MediaChannels = NonNullable<DeviceTemplate['mediaChannels']>

defineProps<{
  deviceId: string
  channels: MediaChannels
  online: boolean
}>()
</script>

<style scoped>
.media-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: repeat(2, minmax(0, 1fr));
  width: 100%;
  height: 100%;
  gap: 1px;
  overflow: hidden;
  background: #020617;
}

.media-grid.single {
  grid-template-columns: minmax(0, 1fr);
  grid-template-rows: minmax(0, 1fr);
}

.media-grid.double {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-template-rows: minmax(0, 1fr);
}

.media-grid.scrolling {
  grid-template-rows: none;
  grid-auto-rows: minmax(230px, 1fr);
  overflow-y: auto;
}

.empty {
  margin: auto;
  color: var(--text-3);
}
</style>
