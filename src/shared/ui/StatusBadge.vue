<template>
  <span class="status-badge" :class="tone">
    <span class="status-dot" />
    <slot>{{ label }}</slot>
  </span>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string
    tone?: 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'simulation'
  }>(),
  {
    label: '',
    tone: 'neutral'
  }
)
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 22px;
  padding: 1px 8px;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  color: var(--text-2);
  background: rgb(148 163 184 / 8%);
  font-size: 11px;
  white-space: nowrap;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentcolor;
}

.success {
  color: var(--color-online);
  border-color: rgb(46 204 113 / 35%);
}

.warning {
  color: var(--color-warn);
  border-color: rgb(245 158 11 / 40%);
}

.danger {
  color: var(--color-danger);
  border-color: rgb(239 68 68 / 45%);
}

.info {
  color: var(--color-accent);
  border-color: rgb(59 130 246 / 40%);
}

.simulation {
  color: #c084fc;
  border-color: rgb(192 132 252 / 45%);
}
</style>
