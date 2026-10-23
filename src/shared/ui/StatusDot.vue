<template>
  <span class="status-dot" :class="tone" :title="title">
    <i class="dot" aria-hidden="true" />
    <span class="label"
      ><slot>{{ label }}</slot></span
    >
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    tone?: 'online' | 'offline' | 'warn' | 'danger' | 'info' | 'muted' | 'simulation'
    label?: string
    title?: string
  }>(),
  { tone: 'info', label: '', title: '' }
)
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
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-info);
  box-shadow: 0 0 0 2px rgb(255 255 255 / 4%);
}

.online .dot {
  background: var(--color-online);
  box-shadow: 0 0 6px rgb(46 204 113 / 50%);
}

.offline .dot {
  background: var(--color-offline);
}

.warn .dot {
  background: var(--color-warn);
  box-shadow: 0 0 6px rgb(245 158 11 / 50%);
}

.danger .dot {
  background: var(--color-danger);
  box-shadow: 0 0 6px rgb(239 68 68 / 55%);
  animation: status-pulse 1.4s infinite;
}

.muted .dot {
  background: var(--text-muted);
}

.simulation .dot {
  background: #c084fc;
  box-shadow: 0 0 6px rgb(192 132 252 / 50%);
}

.label {
  color: var(--text-2);
}

.online .label {
  color: var(--color-online);
}

.offline .label {
  color: var(--color-offline);
}

.warn .label {
  color: var(--color-warn);
}

.danger .label {
  color: var(--color-danger);
}

.simulation .label {
  color: #c084fc;
}

@keyframes status-pulse {
  from {
    box-shadow: 0 0 0 0 rgb(239 68 68 / 60%);
  }

  to {
    box-shadow: 0 0 0 8px rgb(239 68 68 / 0%);
  }
}
</style>
