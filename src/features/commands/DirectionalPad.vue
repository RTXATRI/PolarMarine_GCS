<template>
  <div class="directional-pad">
    <button
      class="control-button forward"
      type="button"
      :disabled="disabled"
      @click="emit('command', 'forward')"
    >
      <el-icon><Top /></el-icon><span>前进</span>
    </button>
    <button
      class="control-button left"
      type="button"
      :disabled="disabled"
      @click="emit('command', 'left')"
    >
      <el-icon><Back /></el-icon><span>左转</span>
    </button>
    <button
      class="control-button stop"
      type="button"
      :disabled="disabled"
      @click="emit('command', 'stop')"
    >
      <el-icon><CircleClose /></el-icon><span>停止</span>
    </button>
    <button
      class="control-button right"
      type="button"
      :disabled="disabled"
      @click="emit('command', 'right')"
    >
      <el-icon><Right /></el-icon><span>右转</span>
    </button>
    <button
      class="control-button backward"
      type="button"
      :disabled="disabled"
      @click="emit('command', 'backward')"
    >
      <el-icon><Bottom /></el-icon><span>后退</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { Back, Bottom, CircleClose, Right, Top } from '@element-plus/icons-vue'

withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false })
const emit = defineEmits<{
  command: [direction: 'forward' | 'backward' | 'left' | 'right' | 'stop']
}>()
</script>

<style scoped>
.directional-pad {
  display: grid;
  grid-template: repeat(3, 88px) / repeat(3, 88px);
  gap: 8px;
}

.control-button {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-direction: column;
  gap: 5px;
  color: var(--text-2);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--bg-panel-2);
  box-shadow: var(--shadow-sm);
  font-family: inherit;
  cursor: pointer;
}

.control-button .el-icon {
  font-size: 22px;
}

.control-button:hover:not(:disabled) {
  color: var(--color-accent);
  border-color: var(--color-accent);
  background: var(--bg-hover);
}

.control-button:active:not(:disabled) {
  transform: translateY(1px);
  box-shadow: inset 0 2px 6px rgb(0 0 0 / 25%);
}

.control-button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.forward {
  grid-area: 1 / 2;
}

.left {
  grid-area: 2 / 1;
}

.stop {
  grid-area: 2 / 2;
  color: #fda4a4;
  border-color: rgb(239 68 68 / 55%);
  background: rgb(239 68 68 / 10%);
}

.stop:hover:not(:disabled) {
  color: #fff;
  border-color: var(--color-danger);
  background: rgb(239 68 68 / 18%);
}

.right {
  grid-area: 2 / 3;
}

.backward {
  grid-area: 3 / 2;
}
</style>
