<template>
  <div class="param-view">
    <div class="toolbar panel">
      <div class="title">
        <el-icon><Setting /></el-icon>
        <span>参数配置</span>
        <span class="muted small">所有改动需点击“写入参数”才会生效</span>
      </div>
      <div class="actions">
        <el-button :icon="Download" :disabled="!canControl" @click="onRead">读取参数</el-button>
        <el-button :icon="Edit" type="primary" :disabled="!canControl || !dirty" @click="onWrite">写入参数</el-button>
        <el-button :icon="UploadFilled" :disabled="!canControl || !hasChange" @click="onSaveToRobot">保存到机器人</el-button>
        <el-button :icon="RefreshRight" :disabled="!canControl" @click="onReset">恢复默认</el-button>
        <el-button :icon="Folder" @click="onImport">导入配置</el-button>
        <el-button :icon="Document" @click="onExport">导出配置</el-button>
        <input ref="fileInput" type="file" accept=".json,application/json" hidden @change="onFileChosen" />
      </div>
    </div>

    <el-alert v-if="!canControl" title="设备未连接或操作通道不可用，参数读写已关闭" type="info" :closable="false" show-icon />
    <el-table :data="params" empty-text="暂无可用参数" border stripe class="params-table">
      <el-table-column prop="name" label="参数名" width="160" />
      <el-table-column label="当前值" width="150">
        <template #default="{ row }: { row: Parameter }">
          <span class="mono">{{ row.currentValue }}</span>
          <span class="unit muted"> {{ row.unit }}</span>
        </template>
      </el-table-column>
      <el-table-column label="修改值" width="200">
        <template #default="{ row }: { row: Parameter }">
          <el-input-number
            v-model="row.editValue"
            :precision="precisionFor(row)"
            :step="stepFor(row)"
            :min="0"
            :disabled="!canControl"
            :class="{ 'value-changed': row.editValue !== row.currentValue }"
          />
        </template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="100" />
      <el-table-column prop="description" label="说明" min-width="240" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }: { row: Parameter }">
          <el-button
            link
            type="primary"
            :disabled="!canControl || row.editValue === row.currentValue"
            @click="writeOne(row)"
          >
            写入
          </el-button>
          <el-button link :disabled="!canControl || row.editValue === row.defaultValue" @click="resetOne(row)">默认</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Setting,
  Download,
  Edit,
  UploadFilled,
  RefreshRight,
  Folder,
  Document
} from '@element-plus/icons-vue'
import { useLogsStore } from '@/stores/logs'
import { useRobotsStore } from '@/stores/robots'
import { fetchParameters, updateParameters } from '@/services/backend-api'
import type { Parameter } from '@/types'
import { useSystemStore } from '@/stores/system'
import { hasCommandChannel } from '@/utils/connection'

const logs = useLogsStore()
const robots = useRobotsStore()
const system = useSystemStore()

const params = ref<Parameter[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
let requestGeneration = 0

const dirty = computed(() => params.value.some(p => p.editValue !== p.currentValue))
const hasChange = computed(() => params.value.some(p => p.editValue !== p.defaultValue))
const canControl = computed(() => system.backendConnected && hasCommandChannel(robots.selected))

function precisionFor(p: Parameter) {
  return p.key === 'max_speed' || p.key === 'rth_speed' ? 2 : 0
}
function stepFor(p: Parameter) {
  return p.key === 'max_speed' || p.key === 'rth_speed' ? 0.1 : 1
}

async function onRead() {
  if (!canControl.value) {
    ElMessage.warning('设备未连接或操作通道不可用')
    return
  }
  const robotId = robots.selectedId
  const generation = ++requestGeneration
  try {
    const next = await fetchParameters(robotId)
    if (generation !== requestGeneration || robots.selectedId !== robotId || !canControl.value) return
    params.value = next
    logs.append('操作', robotId, '读取设备参数')
    ElMessage.success('参数读取成功')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端参数读取失败')
  }
}

async function writeOne(p: Parameter) {
  if (p.editValue === p.currentValue) return
  if (!canControl.value) return
  const robotId = robots.selectedId
  const generation = ++requestGeneration
  try {
    const next = params.value.map(item => item.key === p.key ? { ...item, currentValue: item.editValue } : item)
    const updated = await updateParameters(next, robotId)
    if (generation !== requestGeneration || robots.selectedId !== robotId || !canControl.value) return
    params.value = updated
    logs.append('操作', robotId, `写入参数 ${p.name}`)
    ElMessage.success(`${p.name} 写入成功`)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '参数写入失败')
  }
}

async function onWrite() {
  if (!canControl.value) {
    ElMessage.warning('设备未连接或操作通道不可用')
    return
  }
  const robotId = robots.selectedId
  const generation = ++requestGeneration
  try {
    const updated = params.value.map(p => ({ ...p, currentValue: p.editValue }))
    const response = await updateParameters(updated, robotId)
    if (generation !== requestGeneration || robots.selectedId !== robotId || !canControl.value) return
    params.value = response
    logs.append('操作', robotId, `写入参数 ${params.value.length} 项`)
    ElMessage.success('参数写入成功')
  } catch (error) {
    console.error(error)
    ElMessage.error(error instanceof Error ? error.message : '后端参数写入失败')
  }
}

async function onSaveToRobot() {
  await onWrite()
}

function resetOne(p: Parameter) {
  p.editValue = p.defaultValue
}

async function onReset() {
  try {
    await ElMessageBox.confirm('确认将所有参数恢复为默认值?', '恢复默认', {
      confirmButtonText: '恢复',
      cancelButtonText: '取消',
      type: 'warning'
    })
  } catch {
    return
  }
  for (const p of params.value) p.editValue = p.defaultValue
  logs.append('操作', robots.selectedId || null, '已载入默认参数，等待写入')
  ElMessage.success('默认值已填入修改值，请点击写入参数生效')
}

function onExport() {
  const payload = {
    exportedAt: new Date().toISOString(),
    parameters: params.value.map(p => ({ key: p.key, name: p.name, value: p.currentValue, unit: p.unit }))
  }
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `gcs-parameters-${Date.now()}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
  logs.append('操作', null, '导出参数配置 JSON')
  ElMessage.success('已导出配置')
}

function onImport() {
  fileInput.value?.click()
}

function onFileChosen(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const text = String(reader.result || '')
      const parsed = JSON.parse(text) as { parameters?: Array<{ key: string; value: number }> }
      if (!parsed.parameters || !Array.isArray(parsed.parameters)) throw new Error('字段缺失')
      let count = 0
      for (const inc of parsed.parameters) {
        const p = params.value.find(x => x.key === inc.key)
        if (p && typeof inc.value === 'number') {
          p.editValue = inc.value
          count++
        }
      }
      logs.append('操作', null, `导入参数配置:命中 ${count} 项,需手动写入生效`)
      ElMessage.success(`已导入 ${count} 项参数到"修改值"`)
    } catch (err) {
      console.error(err)
      ElMessage.error('导入失败:文件格式不正确')
    } finally {
      input.value = ''
    }
  }
  reader.readAsText(file)
}

onMounted(() => {
  if (canControl.value) void onRead()
})

watch([() => robots.selectedId, canControl], () => {
  requestGeneration += 1
  params.value = []
  if (canControl.value) void onRead()
})
</script>

<style scoped>
.param-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  gap: 12px;
}
.toolbar .title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-1);
  font-weight: 600;
}
.toolbar .small {
  font-size: 11.5px;
  margin-left: 8px;
}
.actions {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}
.params-table {
  flex: 1;
  min-height: 0;
}
.value-changed :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--color-warn) inset !important;
}
.unit {
  margin-left: 4px;
  font-size: 11px;
}
</style>
