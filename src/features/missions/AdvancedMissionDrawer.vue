<template>
  <el-drawer v-model="visible" title="高级任务编排与历史" size="980px">
    <el-tabs v-model="activeTab" class="advanced-tabs">
      <el-tab-pane label="计划与版本" name="plans">
        <div class="tab-toolbar">
          <span>持久化 MissionPlan；每次修改都会生成新版本。</span>
          <el-button type="primary" size="small" @click="newAdvancedPlan">新建高级计划</el-button>
        </div>
        <el-table :data="missions.plans" height="calc(100vh - 190px)" border>
          <el-table-column prop="name" label="计划" min-width="200" />
          <el-table-column prop="version" label="版本" width="75">
            <template #default="{ row }">v{{ row.version }}</template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90" />
          <el-table-column label="步骤" width="75">
            <template #default="{ row }">{{ row.steps.length }}</template>
          </el-table-column>
          <el-table-column label="设备" min-width="180">
            <template #default="{ row }">{{ planDevices(row).join('、') || '--' }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="180">
            <template #default="{ row }">{{ formatTime(row.updatedAt) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="editPlan(row)">编辑 DAG</el-button>
              <el-button link @click="showVersions(row)">版本</el-button>
              <el-button link type="danger" @click="removePlan(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="DAG 编排" name="dag">
        <div class="dag-editor">
          <div class="dag-header">
            <div>
              <b>{{ editingPlanId ? '编辑计划并生成新版本' : '新建多设备计划' }}</b>
              <span>依赖关系和设备能力由后端再次校验。</span>
            </div>
            <StatusBadge
              :label="editingPlanId ? `计划 ${editingPlanId}` : '尚未持久化'"
              :tone="editingPlanId ? 'info' : 'neutral'"
            />
          </div>
          <el-form label-position="top">
            <div class="two-columns">
              <el-form-item label="计划名称"
                ><el-input v-model="advancedDraft.name"
              /></el-form-item>
              <el-form-item label="说明"
                ><el-input v-model="advancedDraft.description"
              /></el-form-item>
            </div>
          </el-form>
          <div class="step-toolbar">
            <span>{{ advancedDraft.steps.length }} 个步骤</span>
            <el-button size="small" @click="addStep">添加步骤</el-button>
          </div>
          <div class="dag-steps">
            <article v-for="(step, index) in advancedDraft.steps" :key="step.localKey">
              <div class="step-index">{{ index + 1 }}</div>
              <div class="step-fields">
                <el-input v-model="step.id" placeholder="稳定步骤 ID" />
                <el-select v-model="step.stepType">
                  <el-option label="目标点" value="waypoint" />
                  <el-option label="路线" value="route" />
                  <el-option label="返航" value="return_home" />
                  <el-option label="自定义动作" value="custom_action" />
                </el-select>
                <el-select v-model="step.deviceId" filterable placeholder="执行设备">
                  <el-option
                    v-for="device in fleet.devices"
                    :key="device.id"
                    :label="device.displayName"
                    :value="device.id"
                  />
                </el-select>
                <el-input-number
                  v-model="step.timeoutSeconds"
                  :min="1"
                  :max="86400"
                  placeholder="超时秒"
                />
                <el-select v-model="step.dependsOn" multiple collapse-tags placeholder="依赖步骤">
                  <el-option
                    v-for="candidate in advancedDraft.steps.filter(
                      (item) => item.localKey !== step.localKey
                    )"
                    :key="candidate.localKey"
                    :label="candidate.id || candidate.localKey"
                    :value="candidate.id"
                    :disabled="!candidate.id"
                  />
                </el-select>
                <el-input
                  v-model="step.payloadJson"
                  type="textarea"
                  :rows="3"
                  class="mono payload-editor"
                  placeholder='JSON payload，例如 {"latitude":30,"longitude":120}'
                />
              </div>
              <el-button link type="danger" @click="removeStep(index)">删除</el-button>
            </article>
            <div v-if="!advancedDraft.steps.length" class="empty">
              至少添加一个任务步骤；高级编排不会在浏览器内模拟执行。
            </div>
          </div>
          <div class="dag-footer">
            <el-button @click="resetAdvancedDraft">撤销修改</el-button>
            <el-button type="primary" :loading="saving" @click="saveAdvancedPlan">
              {{ editingPlanId ? '保存新版本' : '创建计划' }}
            </el-button>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane label="运行历史与录制" name="history">
        <div class="history-layout">
          <section>
            <h3>任务运行</h3>
            <el-table :data="missions.runs" border max-height="330">
              <el-table-column label="计划" min-width="180">
                <template #default="{ row }">{{
                  missions.plansById[row.missionPlanId]?.name ?? row.missionPlanId
                }}</template>
              </el-table-column>
              <el-table-column prop="missionPlanVersion" label="版本" width="70" />
              <el-table-column prop="status" label="状态" width="100" />
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{
                  formatTime(row.startedAt ?? row.createdAt)
                }}</template>
              </el-table-column>
              <el-table-column label="步骤状态" min-width="240">
                <template #default="{ row }">{{ stepStateSummary(row.stepStates) }}</template>
              </el-table-column>
            </el-table>
          </section>
          <section>
            <div class="recording-heading">
              <h3>MCAP 录制</h3>
              <el-button size="small" :loading="loadingRecordings" @click="loadRecordings"
                >刷新</el-button
              >
            </div>
            <el-table :data="recordings" border max-height="330">
              <el-table-column prop="fileName" label="文件" min-width="230" />
              <el-table-column prop="status" label="状态" width="100" />
              <el-table-column label="大小" width="100">
                <template #default="{ row }">{{ formatBytes(row.sizeBytes) }}</template>
              </el-table-column>
              <el-table-column label="开始时间" width="180">
                <template #default="{ row }">{{ formatTime(row.startedAt) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="175" fixed="right">
                <template #default="{ row }">
                  <el-button
                    link
                    type="primary"
                    :disabled="row.status === 'active'"
                    @click="openPlayback(row)"
                  >
                    回放
                  </el-button>
                  <a
                    v-if="row.status !== 'active'"
                    class="download-link"
                    :href="api.recordingDownloadUrl(row.id)"
                    download
                  >
                    下载 MCAP
                  </a>
                  <span v-else class="muted">录制中</span>
                </template>
              </el-table-column>
            </el-table>
          </section>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="versionsVisible" title="任务版本历史" width="760px" append-to-body>
      <el-table :data="versions" border>
        <el-table-column prop="version" label="版本" width="80" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column label="步骤" width="80">
          <template #default="{ row }">{{ row.steps.length }}</template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="240" />
        <el-table-column label="更新时间" width="180">
          <template #default="{ row }">{{ formatTime(row.updatedAt) }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog v-model="playbackVisible" title="MCAP 索引回放" width="850px" append-to-body>
      <div v-if="playbackMessages.length" class="playback">
        <div class="playback-summary">
          <b>{{ playbackRecording?.fileName }}</b>
          <span>{{ playbackIndex + 1 }} / {{ playbackMessages.length }}</span>
          <span>相对时间 {{ playbackRelativeTime }} ms</span>
        </div>
        <el-slider
          v-model="playbackIndex"
          :min="0"
          :max="Math.max(0, playbackMessages.length - 1)"
          :step="1"
          :show-tooltip="false"
        />
        <code>{{ playbackMessage?.topic }}</code>
        <pre>{{ JSON.stringify(playbackMessage?.payload, null, 2) }}</pre>
      </div>
      <div v-else class="empty">录制文件中没有可读取的完整消息。</div>
    </el-dialog>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { MissionPlan, MissionPlanWrite, Recording, RecordingMessage } from '@/entities/types'
import { useFleetStore } from '@/entities/fleet/store'
import { useMissionStore } from '@/entities/mission/store'
import { api, ApiError } from '@/shared/api/client'
import { formatTime } from '@/shared/lib/presentation'
import StatusBadge from '@/shared/ui/StatusBadge.vue'

interface AdvancedStepDraft {
  localKey: string
  id: string
  stepType: string
  deviceId: string
  dependsOn: string[]
  timeoutSeconds: number
  payloadJson: string
}

const visible = defineModel<boolean>({ default: false })
const fleet = useFleetStore()
const missions = useMissionStore()
const activeTab = ref('plans')
const editingPlanId = ref<string | null>(null)
const saving = ref(false)
const loadingRecordings = ref(false)
const versionsVisible = ref(false)
const versions = ref<MissionPlan[]>([])
const recordings = ref<Recording[]>([])
const playbackVisible = ref(false)
const playbackRecording = ref<Recording | null>(null)
const playbackMessages = ref<RecordingMessage[]>([])
const playbackIndex = ref(0)
const advancedDraft = reactive<{
  name: string
  description: string
  steps: AdvancedStepDraft[]
}>({ name: '', description: '', steps: [] })
const playbackMessage = computed(() => playbackMessages.value[playbackIndex.value] ?? null)
const playbackRelativeTime = computed(() => {
  const first = playbackMessages.value[0]
  const current = playbackMessage.value
  return first && current ? ((current.logTimeNs - first.logTimeNs) / 1_000_000).toFixed(1) : '0.0'
})

watch(visible, (isVisible) => {
  if (isVisible) void load()
})

async function load(): Promise<void> {
  try {
    await missions.load()
    await loadRecordings()
  } catch (error) {
    showError(error, '高级任务数据读取失败')
  }
}

function newAdvancedPlan(): void {
  editingPlanId.value = null
  Object.assign(advancedDraft, { name: '', description: '', steps: [] })
  activeTab.value = 'dag'
}

function editPlan(plan: MissionPlan): void {
  editingPlanId.value = plan.id
  missions.selectedPlanId = plan.id
  advancedDraft.name = plan.name
  advancedDraft.description = plan.description
  advancedDraft.steps = plan.steps.map((step) => ({
    localKey: crypto.randomUUID(),
    id: step.id,
    stepType: step.stepType,
    deviceId: step.deviceId,
    dependsOn: [...(step.dependsOn ?? [])],
    timeoutSeconds: step.timeoutSeconds,
    payloadJson: JSON.stringify(step.payload ?? {}, null, 2)
  }))
  activeTab.value = 'dag'
}

function resetAdvancedDraft(): void {
  const plan = editingPlanId.value ? missions.plansById[editingPlanId.value] : null
  if (plan) editPlan(plan)
  else newAdvancedPlan()
}

function addStep(): void {
  advancedDraft.steps.push({
    localKey: crypto.randomUUID(),
    id: `step-${advancedDraft.steps.length + 1}`,
    stepType: 'waypoint',
    deviceId: fleet.selectedDeviceId,
    dependsOn: [],
    timeoutSeconds: 60,
    payloadJson: '{}'
  })
}

function removeStep(index: number): void {
  const removedId = advancedDraft.steps[index]?.id
  advancedDraft.steps.splice(index, 1)
  if (removedId)
    for (const step of advancedDraft.steps)
      step.dependsOn = step.dependsOn.filter((dependency) => dependency !== removedId)
}

async function saveAdvancedPlan(): Promise<void> {
  saving.value = true
  try {
    const body: MissionPlanWrite = {
      name: advancedDraft.name.trim(),
      description: advancedDraft.description.trim(),
      steps: advancedDraft.steps.map((step) => ({
        id: step.id.trim(),
        stepType: step.stepType,
        deviceId: step.deviceId,
        dependsOn: [...step.dependsOn],
        timeoutSeconds: step.timeoutSeconds,
        payload: parsePayload(step.payloadJson, step.id)
      }))
    }
    const plan = editingPlanId.value
      ? await missions.update(editingPlanId.value, body)
      : await missions.create(body)
    editPlan(plan)
    ElMessage.success('任务计划新版本已持久化')
  } catch (error) {
    showError(error, '高级任务保存失败')
  } finally {
    saving.value = false
  }
}

async function showVersions(plan: MissionPlan): Promise<void> {
  try {
    versions.value = await api.listMissionVersions(plan.id)
    versionsVisible.value = true
  } catch (error) {
    showError(error, '版本历史读取失败')
  }
}

async function removePlan(plan: MissionPlan): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `删除任务“${plan.name}”？已有运行记录时后端会按规则处理。`,
      '删除任务',
      { type: 'warning' }
    )
    await missions.remove(plan.id)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') showError(error, '任务删除失败')
  }
}

async function loadRecordings(): Promise<void> {
  loadingRecordings.value = true
  try {
    recordings.value = await api.listRecordings()
  } finally {
    loadingRecordings.value = false
  }
}

async function openPlayback(recording: Recording): Promise<void> {
  try {
    playbackRecording.value = recording
    playbackMessages.value = await api.recordingMessages(recording.id, 1_000)
    playbackIndex.value = 0
    playbackVisible.value = true
  } catch (error) {
    showError(error, '录制索引读取失败')
  }
}

function parsePayload(json: string, stepId: string): Record<string, unknown> {
  const parsed: unknown = JSON.parse(json)
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
    throw new Error(`步骤 ${stepId || '(未命名)'} 的 payload 必须是 JSON 对象`)
  return parsed as Record<string, unknown>
}

function planDevices(plan: MissionPlan): string[] {
  return [
    ...new Set(
      plan.steps.map((step) => fleet.devicesById[step.deviceId]?.displayName ?? step.deviceId)
    )
  ]
}

function stepStateSummary(states: Record<string, string>): string {
  return Object.entries(states)
    .map(([step, state]) => `${step}: ${state}`)
    .join(' · ')
}

function formatBytes(value: number): string {
  return value < 1024 * 1024
    ? `${(value / 1024).toFixed(1)} KiB`
    : `${(value / 1024 / 1024).toFixed(1)} MiB`
}

function showError(error: unknown, fallback: string): void {
  ElMessage.error(error instanceof ApiError || error instanceof Error ? error.message : fallback)
}
</script>

<style scoped>
.advanced-tabs {
  height: 100%;
}

.tab-toolbar,
.dag-header,
.step-toolbar,
.dag-footer,
.recording-heading,
.playback-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.tab-toolbar {
  margin-bottom: 10px;
  color: var(--text-3);
  font-size: 11px;
}

.dag-editor {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 150px);
  min-height: 0;
}

.dag-header {
  margin-bottom: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel-2);
}

.dag-header div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.dag-header span,
.step-toolbar {
  color: var(--text-3);
  font-size: 10.5px;
}

.two-columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.step-toolbar {
  padding: 8px 0;
  border-top: 1px solid var(--border);
}

.dag-steps {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
}

.dag-steps article {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: start;
  gap: 9px;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.step-index {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  color: var(--color-accent);
  border-radius: 50%;
  background: rgb(59 130 246 / 12%);
}

.step-fields {
  display: grid;
  grid-template-columns: 1.2fr 125px 1.2fr 120px 1.2fr;
  gap: 7px;
}

.payload-editor {
  grid-column: 1 / -1;
}

.dag-footer {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}

.history-layout {
  display: flex;
  flex-direction: column;
  gap: 18px;
  height: calc(100vh - 165px);
  overflow-y: auto;
}

.history-layout h3 {
  margin: 0 0 8px;
  font-size: 13px;
}

.recording-heading h3 {
  margin: 0;
}

.download-link {
  margin-left: 8px;
  color: var(--color-accent);
  font-size: 11px;
}

.playback {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.playback-summary span {
  color: var(--text-3);
  font-size: 10.5px;
}

.playback code {
  color: var(--color-accent);
}

.playback pre {
  min-height: 280px;
  max-height: 440px;
  margin: 0;
  padding: 12px;
  overflow: auto;
  color: var(--text-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--code-bg);
}

.empty {
  padding: 24px;
  color: var(--text-3);
  text-align: center;
}
</style>
