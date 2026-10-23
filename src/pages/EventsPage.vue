<template>
  <div class="events-page">
    <section class="alarms panel">
      <div class="header">
        <div class="title">
          <el-icon><Bell /></el-icon>
          <span>当前报警</span>
          <el-tag v-if="events.activeAlarms.length" size="small" type="danger" effect="dark">
            {{ events.activeAlarms.length }} 条未确认
          </el-tag>
          <el-tag v-else size="small" type="success">全部已确认</el-tag>
        </div>
        <div class="actions">
          <el-switch v-model="activeOnly" active-text="仅未确认" />
          <el-button
            size="small"
            :disabled="!visibleUnacknowledged.length"
            :loading="acknowledgingAll"
            @click="acknowledgeVisible"
          >
            确认筛选项
          </el-button>
          <el-button size="small" @click="downloadSupportBundle">导出支持包</el-button>
        </div>
      </div>
      <el-table :data="filteredAlarms" size="small" border max-height="240">
        <el-table-column label="等级" width="100">
          <template #default="{ row }">
            <span class="tag-pill" :class="alarmTone(row.severity)">
              {{ alarmSeverityLabel(row.severity) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="设备" width="150">
          <template #default="{ row }">
            <span class="mono">{{ row.deviceId ?? 'SYSTEM' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="code" label="代码" min-width="170" />
        <el-table-column prop="message" label="报警内容" min-width="280" />
        <el-table-column label="报警时间" width="180">
          <template #default="{ row }"
            ><span class="mono">{{ formatTime(row.createdAt) }}</span></template
          >
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.acknowledged ? 'success' : 'warning'" size="small" effect="dark">
              {{ row.acknowledged ? '已确认' : '未确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :disabled="row.acknowledged || acknowledgingId === row.id"
              @click="acknowledge(row.id)"
            >
              确认
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="history panel">
      <div class="header">
        <div class="title">
          <el-icon><Document /></el-icon>
          <span>历史日志</span>
          <small>共 {{ filteredEvents.length }} 条 · 持久化追加记录 · 最新在前</small>
        </div>
        <div class="filters">
          <el-select v-model="deviceFilter" clearable placeholder="按设备筛选" size="small">
            <el-option
              v-for="device in fleet.devices"
              :key="device.id"
              :label="device.displayName"
              :value="device.id"
            />
          </el-select>
          <el-select v-model="categoryFilter" clearable placeholder="按类型筛选" size="small">
            <el-option label="操作" value="operation" />
            <el-option label="通信" value="communication" />
            <el-option label="报警" value="alarm" />
            <el-option label="系统" value="system" />
          </el-select>
          <el-input v-model="search" clearable size="small" placeholder="搜索事件或内容" />
          <el-button size="small" :icon="Download" @click="exportFilteredEvents"
            >导出筛选结果</el-button
          >
        </div>
      </div>
      <el-table :data="filteredEvents" size="small" border height="100%" class="events-table">
        <el-table-column label="时间" width="180">
          <template #default="{ row }"
            ><span class="mono">{{ formatTime(row.occurredAt) }}</span></template
          >
        </el-table-column>
        <el-table-column label="类型" width="92">
          <template #default="{ row }">
            <span class="tag-pill" :class="eventTone(eventCategory(row.type))">
              {{ eventCategoryLabel(eventCategory(row.type)) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="设备/对象" min-width="170">
          <template #default="{ row }">
            <div class="aggregate">
              <b class="mono">{{ row.aggregateId }}</b>
              <small>{{ row.aggregateType }} · r{{ row.aggregateRevision }}</small>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="事件" min-width="230">
          <template #default="{ row }">
            <div class="event-name">
              <b>{{ eventLabel(row.type) }}</b
              ><code>{{ row.type }}</code>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="内容" min-width="320">
          <template #default="{ row }">
            <span class="payload">{{ payloadSummary(row.payload) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="游标" width="88">
          <template #default="{ row }"
            ><span class="mono">#{{ row.eventCursor }}</span></template
          >
        </el-table-column>
      </el-table>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Bell, Document, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { Alarm } from '@/entities/types'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import { api, ApiError } from '@/shared/api/client'
import { eventLabel, formatTime } from '@/shared/lib/presentation'

type EventCategory = 'operation' | 'communication' | 'alarm' | 'system'

const events = useEventsStore()
const fleet = useFleetStore()
const activeOnly = ref(true)
const deviceFilter = ref('')
const categoryFilter = ref<EventCategory | ''>('')
const search = ref('')
const acknowledgingId = ref<string | null>(null)
const acknowledgingAll = ref(false)

const filteredAlarms = computed(() =>
  events.alarms.filter((alarm) => {
    if (activeOnly.value && alarm.acknowledged) return false
    if (deviceFilter.value && alarm.deviceId !== deviceFilter.value) return false
    return true
  })
)
const visibleUnacknowledged = computed(() =>
  filteredAlarms.value.filter((alarm) => !alarm.acknowledged)
)
const filteredEvents = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('zh-CN')
  return events.events.filter((event) => {
    if (
      deviceFilter.value &&
      event.aggregateId !== deviceFilter.value &&
      event.payload.deviceId !== deviceFilter.value
    )
      return false
    if (categoryFilter.value && eventCategory(event.type) !== categoryFilter.value) return false
    if (!query) return true
    return `${event.type} ${event.aggregateId} ${JSON.stringify(event.payload)}`
      .toLocaleLowerCase('zh-CN')
      .includes(query)
  })
})

async function acknowledge(alarmId: string): Promise<void> {
  acknowledgingId.value = alarmId
  try {
    events.upsertAlarm(await api.acknowledgeAlarm(alarmId))
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : '告警确认失败')
  } finally {
    acknowledgingId.value = null
  }
}

async function acknowledgeVisible(): Promise<void> {
  acknowledgingAll.value = true
  let failed = 0
  for (const alarm of visibleUnacknowledged.value) {
    try {
      events.upsertAlarm(await api.acknowledgeAlarm(alarm.id))
    } catch {
      failed += 1
    }
  }
  acknowledgingAll.value = false
  if (failed) ElMessage.error(`${failed} 条告警确认失败，请检查后端事件`)
  else ElMessage.success('筛选范围内的告警已全部确认')
}

function downloadSupportBundle(): void {
  const anchor = document.createElement('a')
  anchor.href = api.supportBundleUrl()
  anchor.download = ''
  anchor.click()
}

function exportFilteredEvents(): void {
  const url = URL.createObjectURL(
    new Blob(
      [
        JSON.stringify(
          {
            schemaVersion: '1.0',
            exportedAt: new Date().toISOString(),
            filters: {
              deviceId: deviceFilter.value || null,
              category: categoryFilter.value || null,
              search: search.value || null
            },
            events: filteredEvents.value
          },
          null,
          2
        )
      ],
      { type: 'application/json' }
    )
  )
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `polarmarine-events-${Date.now()}.json`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function eventCategory(type: string): EventCategory {
  if (type.startsWith('alarm.')) return 'alarm'
  if (type.startsWith('link_') || type.startsWith('telemetry.') || type.includes('route'))
    return 'communication'
  if (type.startsWith('command.') || type.startsWith('mission_') || type.startsWith('parameters.'))
    return 'operation'
  return 'system'
}

function eventCategoryLabel(category: EventCategory): string {
  return { operation: '操作', communication: '通信', alarm: '报警', system: '系统' }[category]
}

function eventTone(category: EventCategory): string {
  return category === 'alarm'
    ? 'warn'
    : category === 'operation' || category === 'communication'
      ? 'info'
      : 'offline'
}

function alarmTone(severity: Alarm['severity']): string {
  return severity === 'critical' ? 'danger' : severity === 'warning' ? 'warn' : 'info'
}

function alarmSeverityLabel(severity: Alarm['severity']): string {
  return severity === 'critical' ? '严重' : severity === 'warning' ? '警告' : '提示'
}

function payloadSummary(payload: Record<string, unknown>): string {
  const entries = Object.entries(payload)
    .filter(([key]) => key !== 'schemaVersion')
    .slice(0, 5)
    .map(([key, value]) => `${key}=${scalar(value)}`)
  return entries.join(' · ') || '--'
}

function scalar(value: unknown): string {
  if (value == null) return '--'
  return typeof value === 'object' ? JSON.stringify(value) : String(value)
}
</script>

<style scoped>
.events-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.alarms {
  flex: 0 0 auto;
  padding: 10px 12px 12px;
}

.history {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
  padding: 10px 12px 12px;
}

.header,
.title,
.actions,
.filters {
  display: flex;
  align-items: center;
}

.header {
  justify-content: space-between;
  gap: 12px;
  min-height: 34px;
  padding-bottom: 8px;
}

.title {
  gap: 8px;
  color: var(--text-1);
  font-weight: 600;
  white-space: nowrap;
}

.title small {
  color: var(--text-3);
  font-size: 11px;
  font-weight: 400;
}

.actions,
.filters {
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.filters .el-select {
  width: 150px;
}

.filters .el-input {
  width: 220px;
}

.events-table {
  flex: 1;
  min-height: 0;
}

.aggregate,
.event-name {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.aggregate small,
.event-name code {
  color: var(--text-3);
  font-size: 9.5px;
}

.event-name code {
  color: var(--color-accent);
}

.payload {
  display: block;
  overflow: hidden;
  color: var(--text-2);
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (width <= 1450px) {
  .title small {
    display: none;
  }

  .filters .el-input {
    width: 170px;
  }
}
</style>
