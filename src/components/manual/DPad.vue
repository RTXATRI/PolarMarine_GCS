<template>
  <div class="dpad">
    <button class="btn fwd" :disabled="disabled" @click="emitDir('前进')">
      <el-icon><Top /></el-icon>
      <span>前进</span>
    </button>
    <button class="btn left" :disabled="disabled" @click="emitDir('左转')">
      <el-icon><Back /></el-icon>
      <span>左转</span>
    </button>
    <button class="btn stop" :disabled="disabled" @click="emitDir('停止')">
      <el-icon><CircleClose /></el-icon>
      <span>停止</span>
    </button>
    <button class="btn right" :disabled="disabled" @click="emitDir('右转')">
      <el-icon><Right /></el-icon>
      <span>右转</span>
    </button>
    <button class="btn back" :disabled="disabled" @click="emitDir('后退')">
      <el-icon><Bottom /></el-icon>
      <span>后退</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { Top, Bottom, Back, Right, CircleClose } from '@element-plus/icons-vue'

interface Props {
  disabled?: boolean
}
withDefaults(defineProps<Props>(), { disabled: false })
const emit = defineEmits<{ (e: 'cmd', dir: '前进' | '后退' | '左转' | '右转' | '停止'): void }>()

function emitDir(d: '前进' | '后退' | '左转' | '右转' | '停止') {
  emit('cmd', d)
}
</script>

<style scoped>
.dpad {
  display: grid;
  grid-template-columns: repeat(3, 88px);
  grid-template-rows: repeat(3, 88px);
  gap: 8px;
  width: max-content;
}
.btn {
  background: var(--bg-panel-2);
  border: 1px solid var(--border-strong);
  color: var(--text-1);
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  display: grid;
  place-items: center;
  gap: 4px;
  transition: transform 0.05s ease, background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
  user-select: none;
}
.btn :deep(.el-icon) {
  font-size: 22px;
}
.btn:hover:not(:disabled) {
  background: var(--bg-hover);
  border-color: var(--color-accent);
  color: var(--color-accent);
}
.btn:active:not(:disabled) {
  transform: translateY(1px);
  box-shadow: inset 0 2px 6px rgba(0, 0, 0, 0.25);
}
.btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.btn.fwd {
  grid-column: 2;
  grid-row: 1;
}
.btn.left {
  grid-column: 1;
  grid-row: 2;
}
.btn.stop {
  grid-column: 2;
  grid-row: 2;
  background: rgba(239, 68, 68, 0.1);
  border-color: rgba(239, 68, 68, 0.55);
  color: #fda4a4;
}
.btn.stop:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.18);
  color: #fff;
  border-color: var(--color-danger);
}
.btn.right {
  grid-column: 3;
  grid-row: 2;
}
.btn.back {
  grid-column: 2;
  grid-row: 3;
}
</style>
