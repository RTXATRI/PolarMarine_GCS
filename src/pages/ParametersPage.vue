<template>
  <div class="parameters-page">
    <section class="toolbar panel">
      <div class="title">
        <el-icon><Setting /></el-icon>
        <span>参数配置</span>
        <small>修改值不会自动生效；写入后仍需等待设备逐项确认</small>
      </div>
      <div class="actions">
        <el-button
          :icon="Download"
          :disabled="!canRead"
          :loading="refreshing"
          @click="refreshFromDevice"
        >
          读取参数
        </el-button>
        <el-button
          :icon="Edit"
          type="primary"
          :disabled="!canWrite || !changedCount"
          :loading="saving"
          @click="saveAll"
        >
          写入参数
        </el-button>
        <el-tooltip :content="persistDisabledReason || '要求设备将已确认参数持久化'">
          <span>
            <el-button
              :icon="UploadFilled"
              :disabled="Boolean(persistDisabledReason)"
              :loading="persisting"
              @click="persistToDevice"
            >
              保存到设备
            </el-button>
          </span>
        </el-tooltip>
        <el-button :icon="RefreshRight" :disabled="!parameters.length" @click="loadDefaults">
          恢复默认
        </el-button>
        <el-button :icon="Folder" @click="openImport">导入配置</el-button>
        <el-button :icon="Document" :disabled="!parameters.length" @click="exportParameters">
          导出配置
        </el-button>
        <input
          ref="fileInput"
          hidden
          type="file"
          accept=".json,application/json"
          @change="importFile"
        />
      </div>
    </section>

    <el-alert
      v-if="!fleet.selectedDevice"
      title="请先选择设备"
      type="info"
      :closable="false"
      show-icon
    />
    <el-alert
      v-else-if="!canWrite"
      :title="writeDisabledReason"
      type="info"
      :closable="false"
      show-icon
    />

    <section class="table-panel panel">
      <div class="table-summary">
        <div>
          <b>{{ fleet.selectedDevice?.displayName ?? '未选择设备' }}</b>
          <span class="mono">{{ fleet.selectedDeviceId || '--' }}</span>
        </div>
        <div>
          <span>{{ parameters.length }} 项参数</span>
          <span v-if="changedCount" class="changed">{{ changedCount }} 项差异</span>
          <StatusBadge
            v-if="latestCommand"
            :label="commandStatusLabel(latestCommand.status)"
            :tone="commandTone(latestCommand.status)"
          />
        </div>
      </div>

      <el-table
        v-loading="loading"
        :data="parameters"
        empty-text="当前设备模板没有参数定义"
        border
        stripe
        height="100%"
        class="parameter-table"
      >
        <el-table-column label="参数" min-width="210">
          <template #default="{ row }">
            <div class="parameter-name">
              <b>{{ row.definition.displayName }}</b>
              <code>{{ row.definition.key }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="当前值" min-width="145">
          <template #default="{ row }">
            <span class="mono">{{ displayValue(row.value) }}</span>
            <small class="unit">{{ row.definition.unit ?? '' }}</small>
            <small class="source">{{
              row.source === 'device_confirmed' ? '设备已确认' : '模板默认值'
            }}</small>
          </template>
        </el-table-column>
        <el-table-column label="修改值" min-width="205">
          <template #default="{ row }">
            <el-switch
              v-if="row.definition.valueType === 'boolean'"
              v-model="drafts[row.definition.key]"
              :disabled="!canWrite || row.definition.readOnly"
            />
            <el-select
              v-else-if="row.definition.valueType === 'enum'"
              v-model="drafts[row.definition.key]"
              :disabled="!canWrite || row.definition.readOnly"
            >
              <el-option
                v-for="option in row.definition.enumValues"
                :key="option"
                :label="option"
                :value="option"
              />
            </el-select>
            <el-input-number
              v-else-if="
                row.definition.valueType === 'number' || row.definition.valueType === 'integer'
              "
              v-model="drafts[row.definition.key]"
              :min="row.definition.minimum ?? undefined"
              :max="row.definition.maximum ?? undefined"
              :step="row.definition.step ?? 1"
              :precision="
                row.definition.valueType === 'integer' ? 0 : precision(row.definition.step)
              "
              :disabled="!canWrite || row.definition.readOnly"
              :class="{ 'value-changed': drafts[row.definition.key] !== row.value }"
            />
            <el-input
              v-else
              v-model="drafts[row.definition.key]"
              :disabled="!canWrite || row.definition.readOnly"
              :class="{ 'value-changed': drafts[row.definition.key] !== row.value }"
            />
          </template>
        </el-table-column>
        <el-table-column prop="definition.unit" label="单位" width="78" />
        <el-table-column label="约束" min-width="145">
          <template #default="{ row }">
            <div class="constraints mono">
              <span v-if="row.definition.minimum != null">min {{ row.definition.minimum }}</span>
              <span v-if="row.definition.maximum != null">max {{ row.definition.maximum }}</span>
              <span v-if="row.definition.step != null">step {{ row.definition.step }}</span>
              <span v-if="row.definition.enumValues?.length">{{
                row.definition.enumValues.join(' / ')
              }}</span>
              <span v-if="row.definition.readOnly">只读</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="definition.description" label="说明" min-width="220" />
        <el-table-column label="设备结果" width="105">
          <template #default="{ row }">
            <span
              v-if="parameterResult(row.definition.key)"
              class="result"
              :class="parameterResult(row.definition.key)?.tone"
            >
              {{ parameterResult(row.definition.key)?.text }}
            </span>
            <span v-else class="muted">--</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="
                !canWrite ||
                row.definition.readOnly ||
                drafts[row.definition.key] === row.value ||
                saving
              "
              @click="saveOne(row)"
            >
              写入
            </el-button>
            <el-button
              link
              :disabled="
                row.definition.readOnly ||
                drafts[row.definition.key] === row.definition.defaultValue
              "
              @click="drafts[row.definition.key] = normalizeValue(row.definition.defaultValue)"
            >
              默认
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import {
  Document,
  Download,
  Edit,
  Folder,
  RefreshRight,
  Setting,
  UploadFilled
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { CommandStatus, ParameterState } from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import { commandStatusLabel, useCommand } from '@/features/commands/use-command'
import { api, ApiError } from '@/shared/api/client'
import { hasCapability } from '@/shared/lib/device-view'
import StatusBadge from '@/shared/ui/StatusBadge.vue'

type ParameterDraft = string | number | boolean

const fleet = useFleetStore()
const persistCommand = useCommand()
const parameters = ref<ParameterState[]>([])
const drafts = reactive<Record<string, ParameterDraft>>({})
const loading = ref(false)
const saving = ref(false)
const refreshing = ref(false)
const persisting = computed(() => persistCommand.submitting.value)
const commandId = ref<string | null>(null)
const fileInput = ref<HTMLInputElement | null>(null)
let requestGeneration = 0

const latestCommand = computed(() =>
  commandId.value ? (fleet.commandsById[commandId.value] ?? null) : null
)
const canRead = computed(
  () => fleet.selectedOnline && hasCapability(fleet.selectedTemplate, 'parameters.read')
)
const canWrite = computed(
  () => fleet.selectedOnline && hasCapability(fleet.selectedTemplate, 'parameters.write')
)
const changed = computed(() =>
  Object.fromEntries(
    parameters.value
      .filter((item) => !item.definition.readOnly && drafts[item.definition.key] !== item.value)
      .map((item) => [item.definition.key, drafts[item.definition.key]])
  )
)
const changedCount = computed(() => Object.keys(changed.value).length)
const writeDisabledReason = computed(() => {
  if (!fleet.backendConnected) return '核心服务已断开，参数读写已关闭'
  if (!fleet.selectedOnline) return '设备离线或没有健康参数链路，参数写入已关闭'
  if (!hasCapability(fleet.selectedTemplate, 'parameters.write'))
    return '当前设备模板未声明参数写入能力'
  return ''
})
const persistDisabledReason = computed(() => {
  if (!fleet.selectedOnline) return '设备离线或没有健康链路'
  if (!hasCapability(fleet.selectedTemplate, 'parameters.persist'))
    return '当前设备模板未声明参数持久化能力'
  if (changedCount.value) return '请先写入并等待设备确认所有差异'
  return ''
})

watch(() => fleet.selectedDeviceId, load, { immediate: true })
watch(
  () => latestCommand.value?.status,
  (status) => {
    if (status === 'completed') void load()
  }
)

async function load(): Promise<void> {
  requestGeneration += 1
  const generation = requestGeneration
  const deviceId = fleet.selectedDeviceId
  parameters.value = []
  clearDrafts()
  commandId.value = null
  if (!deviceId) return
  loading.value = true
  try {
    const result = await api.listParameters(deviceId)
    if (generation !== requestGeneration || deviceId !== fleet.selectedDeviceId) return
    parameters.value = result
    restoreDrafts()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '参数列表读取失败')
  } finally {
    if (generation === requestGeneration) loading.value = false
  }
}

async function refreshFromDevice(): Promise<void> {
  if (!canRead.value) return
  refreshing.value = true
  try {
    const result = await api.refreshParameters(fleet.selectedDeviceId)
    fleet.upsertCommand(result)
    commandId.value = result.id
    if (result.status === 'completed') await load()
    else ElMessage.info('参数读取请求已提交，正在等待设备返回实际值')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '参数读取请求失败')
  } finally {
    refreshing.value = false
  }
}

async function saveAll(): Promise<void> {
  await writeValues(changed.value)
}

async function saveOne(item: ParameterState): Promise<void> {
  const key = item.definition.key
  await writeValues({ [key]: drafts[key] })
}

async function writeValues(values: Record<string, unknown>): Promise<void> {
  if (!canWrite.value || !Object.keys(values).length) return
  const validationError = validateValues(values)
  if (validationError) {
    ElMessage.error(validationError)
    return
  }
  saving.value = true
  try {
    const result = await api.writeParameters(fleet.selectedDeviceId, values)
    fleet.upsertCommand(result)
    commandId.value = result.id
    ElMessage.info('参数差异已提交，正在等待设备逐项确认')
    if (result.status === 'completed') await load()
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '参数写入失败')
  } finally {
    saving.value = false
  }
}

async function persistToDevice(): Promise<void> {
  if (persistDisabledReason.value) return
  const result = await persistCommand.submit(fleet.selectedDeviceId, 'custom_action', {
    capability: 'parameters.persist',
    action: 'persist_parameters'
  })
  if (result) {
    commandId.value = result.id
    ElMessage.info('参数持久化请求已提交，正在等待设备确认')
  }
}

async function loadDefaults(): Promise<void> {
  try {
    await ElMessageBox.confirm('把模板默认值填入“修改值”？这不会立即写入设备。', '恢复默认值', {
      type: 'warning'
    })
  } catch {
    return
  }
  for (const item of parameters.value) {
    if (!item.definition.readOnly)
      drafts[item.definition.key] = normalizeValue(item.definition.defaultValue)
  }
  ElMessage.info('默认值已载入草稿；请检查差异后再写入')
}

function restoreDrafts(): void {
  clearDrafts()
  for (const item of parameters.value) {
    drafts[item.definition.key] = normalizeValue(item.value)
  }
}

function clearDrafts(): void {
  for (const key of Object.keys(drafts)) delete drafts[key]
}

function openImport(): void {
  fileInput.value?.click()
}

function importFile(event: Event): void {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = () => {
    try {
      const payload = JSON.parse(String(reader.result ?? '')) as {
        parameters?: Array<{ key?: unknown; value?: unknown }>
      }
      if (!Array.isArray(payload.parameters)) throw new Error('缺少 parameters 数组')
      let matched = 0
      for (const imported of payload.parameters) {
        if (typeof imported.key !== 'string') continue
        const parameter = parameters.value.find(
          (item) => item.definition.key === imported.key && !item.definition.readOnly
        )
        if (!parameter) continue
        const value = normalizeImportedValue(imported.value)
        const error = validateValue(parameter, value)
        if (error) throw new Error(`${imported.key}: ${error}`)
        drafts[imported.key] = value
        matched += 1
      }
      ElMessage.success(`已导入 ${matched} 项到修改值；尚未写入设备`)
    } catch (error) {
      ElMessage.error(error instanceof Error ? `导入失败：${error.message}` : '导入失败')
    } finally {
      input.value = ''
    }
  }
  reader.readAsText(file)
}

function exportParameters(): void {
  const payload = {
    schemaVersion: '1.0',
    deviceId: fleet.selectedDeviceId,
    exportedAt: new Date().toISOString(),
    parameters: parameters.value.map((item) => ({
      key: item.definition.key,
      value: item.value,
      source: item.source
    }))
  }
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  )
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `polarmarine-parameters-${fleet.selectedDeviceId}-${Date.now()}.json`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function validateValues(values: Record<string, unknown>): string | null {
  for (const [key, value] of Object.entries(values)) {
    const parameter = parameters.value.find((item) => item.definition.key === key)
    if (!parameter) return `未知参数 ${key}`
    const error = validateValue(parameter, value)
    if (error) return `${parameter.definition.displayName}：${error}`
  }
  return null
}

function validateValue(parameter: ParameterState, value: unknown): string | null {
  const definition = parameter.definition
  if (definition.valueType === 'boolean') return typeof value === 'boolean' ? null : '必须是布尔值'
  if (definition.valueType === 'number' || definition.valueType === 'integer') {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '必须是有效数字'
    if (definition.valueType === 'integer' && !Number.isInteger(value)) return '必须是整数'
    if (definition.minimum != null && value < definition.minimum)
      return `不得小于 ${definition.minimum}`
    if (definition.maximum != null && value > definition.maximum)
      return `不得大于 ${definition.maximum}`
    return null
  }
  if (typeof value !== 'string') return '必须是文本'
  if (definition.valueType === 'enum' && !definition.enumValues?.includes(value))
    return '不在允许的枚举值内'
  return null
}

function parameterResult(key: string): { text: string; tone: string } | null {
  const raw = latestCommand.value?.result.parameterResults
  if (!raw || typeof raw !== 'object') return null
  const outcome = (raw as Record<string, unknown>)[key]
  if (!outcome || typeof outcome !== 'object') return null
  const status = String((outcome as Record<string, unknown>).status ?? 'unknown')
  return ['applied', 'completed', 'confirmed'].includes(status)
    ? { text: '已应用', tone: 'success' }
    : { text: '失败', tone: 'danger' }
}

function commandTone(
  status: CommandStatus
): 'neutral' | 'success' | 'warning' | 'danger' | 'info' | 'simulation' {
  if (status === 'completed') return 'success'
  if (['rejected', 'timed_out', 'state_unconfirmed'].includes(status)) return 'danger'
  if (status === 'accepted' || status === 'in_progress') return 'info'
  return 'neutral'
}

function normalizeValue(value: unknown): ParameterDraft {
  return typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string'
    ? value
    : ''
}

function normalizeImportedValue(value: unknown): ParameterDraft {
  if (typeof value === 'boolean' || typeof value === 'number' || typeof value === 'string')
    return value
  throw new Error('参数值必须是字符串、数字或布尔值')
}

function displayValue(value: unknown): string {
  if (value == null) return '--'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}

function precision(step: number | null | undefined): number {
  if (step == null || Number.isInteger(step)) return 0
  return Math.min(6, String(step).split('.')[1]?.length ?? 0)
}
</script>

<style scoped>
.parameters-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex: 0 0 auto;
  padding: 10px 14px;
}

.title,
.actions,
.table-summary,
.table-summary > div {
  display: flex;
  align-items: center;
}

.title {
  gap: 8px;
  color: var(--text-1);
  font-weight: 600;
  white-space: nowrap;
}

.title small {
  margin-left: 8px;
  color: var(--text-3);
  font-size: 11px;
  font-weight: 400;
}

.actions {
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 6px;
}

.table-panel {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.table-summary {
  justify-content: space-between;
  flex: 0 0 42px;
  min-height: 42px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border);
}

.table-summary > div {
  gap: 9px;
}

.table-summary span {
  color: var(--text-3);
  font-size: 10.5px;
}

.table-summary .changed {
  color: var(--color-warn);
}

.parameter-table {
  flex: 1;
  min-height: 0;
}

.parameter-name {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.parameter-name code {
  color: var(--color-accent);
  font-size: 10px;
}

.unit {
  margin-left: 4px;
  color: var(--text-3);
}

.source {
  display: block;
  margin-top: 3px;
  color: var(--text-muted);
  font-size: 9px;
}

.constraints {
  display: flex;
  flex-wrap: wrap;
  gap: 5px 8px;
  color: var(--text-3);
  font-size: 9.5px;
}

.value-changed :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px var(--color-warn) inset !important;
}

.result {
  display: inline-flex;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 10px;
}

.result.success {
  color: var(--color-online);
  background: rgb(46 204 113 / 10%);
}

.result.danger {
  color: var(--color-danger);
  background: rgb(239 68 68 / 10%);
}

@media (width <= 1450px) {
  .title small {
    display: none;
  }
}
</style>
