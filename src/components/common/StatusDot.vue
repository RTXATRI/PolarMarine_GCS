<template>
  <span class="status-dot" :class="tone" :title="title">
    <i class="dot" />
    <span class="label"><slot>{{ label }}</slot></span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  tone?: 'online' | 'offline' | 'warn' | 'danger' | 'info' | 'muted'
  label?: string
  title?: string
}
const props = withDefaults(defineProps<Props>(), { tone: 'info', label: '' })
const tone = computed(() => props.tone)
</script>

<style scoped>
.status-dot {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12.5px;
  white-space: nowrap;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
  background: var(--color-info);
  box-shadow: 0 0 0 2px rgba(255, 255, 255, 0.04);
}
.online .dot {
  background: var(--color-online);
  box-shadow: 0 0 6px rgba(46, 204, 113, 0.5);
}
.offline .dot {
  background: var(--color-offline);
}
.warn .dot {
  background: var(--color-warn);
  box-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
}
.danger .dot {
  background: var(--color-danger);
  box-shadow: 0 0 6px rgba(239, 68, 68, 0.55);
  animation: pulse 1.4s infinite;
}
.muted .dot {
  background: var(--text-muted);
}
.label {
  color: var(--text-2);
}
.online .label {
  color: var(--color-online);
}
.warn .label {
  color: var(--color-warn);
}
.danger .label {
  color: var(--color-danger);
}
.offline .label {
  color: var(--color-offline);
}

@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.6);
  }
  100% {
    box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
  }
}
</style>
