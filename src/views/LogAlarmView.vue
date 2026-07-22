<template>
  <div class="log-view">
    <div class="alarms panel">
      <div class="header">
        <div class="title">
          <el-icon><Bell /></el-icon>
          <span>当前报警</span>
          <el-tag size="small" type="danger" effect="dark" v-if="logs.activeAlarms.length">
            {{ logs.activeAlarms.length }} 条未确认
          </el-tag>
          <el-tag size="small" v-else>全部已确认</el-tag>
        </div>
        <div class="actions">
          <el-button size="small" :disabled="!logs.activeAlarms.length" @click="onAckAll">全部确认</el-button>
          <el-button size="small" :disabled="!logs.alarms.length" @click="onClearAlarms">清空报警</el-button>
        </div>
      </div>
      <el-table :data="logs.alarms" size="small" border max-height="240">
        <el-table-column label="等级" width="100">
          <template #default="{ row }: { row: Alarm }">
            <span class="tag-pill" :class="alarmTone(row.level)">{{ row.level }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="robotId" label="机器人" width="120" />
        <el-table-column prop="content" label="报警内容" min-width="240" />
        <el-table-column label="报警时间" width="180">
          <template #default="{ row }: { row: Alarm }">
            <span class="mono">{{ formatTime(row.time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="是否确认" width="110">
          <template #default="{ row }: { row: Alarm }">
            <el-tag :type="row.acknowledged ? 'success' : 'warning'" size="small" effect="dark">
              {{ row.acknowledged ? '已确认' : '未确认' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }: { row: Alarm }">
            <el-button link type="primary" :disabled="row.acknowledged" @click="logs.ackAlarm(row.id)">确认</el-button>
          </template>
        </el-table-column>
        <template #empty>
          <div class="muted">暂无报警</div>
        </template>
      </el-table>
    </div>

    <div class="history panel">
      <div class="header">
        <div class="title">
          <el-icon><Document /></el-icon>
          <span>历史日志</span>
          <span class="muted small">共 {{ filtered.length }} 条 · 最新在前</span>
        </div>
        <div class="filters">
          <el-select v-model="filterRobotId" clearable placeholder="按机器人筛选" size="small" style="width: 160px">
            <el-option v-for="r in robots.robots" :key="r.id" :label="r.id" :value="r.id" />
          </el-select>
          <el-select v-model="filterType" clearable placeholder="按类型筛选" size="small" style="width: 140px">
            <el-option label="操作" value="操作" />
            <el-option label="通信" value="通信" />
            <el-option label="报警" value="报警" />
            <el-option label="系统" value="系统" />
          </el-select>
          <el-button size="small" :icon="Delete" @click="onClearLogs">清空日志</el-button>
        </div>
      </div>
      <el-table :data="filtered" size="small" border class="logs-table" :height="logsHeight">
        <el-table-column label="时间" width="180">
          <template #default="{ row }: { row: LogEntry }">
            <span class="mono">{{ formatTime(row.time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90">
          <template #default="{ row }: { row: LogEntry }">
            <span class="tag-pill" :class="typeTone(row.type)">{{ row.type }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="robotId" label="机器人" width="110">
          <template #default="{ row }: { row: LogEntry }">
            <span class="mono">{{ row.robotId ?? '----' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="content" label="内容" min-width="240" />
        <template #empty>
          <div class="muted">暂无日志</div>
        </template>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ElMessageBox } from 'element-plus'
import { Bell, Document, Delete } from '@element-plus/icons-vue'
import { useLogsStore } from '@/stores/logs'
import { useRobotsStore } from '@/stores/robots'
import type { Alarm, AlarmLevel, LogEntry, LogType, RobotId } from '@/types'

const logs = useLogsStore()
const robots = useRobotsStore()

const filterRobotId = ref<RobotId | ''>('')
const filterType = ref<LogType | ''>('')
const logsHeight = ref(360)

const filtered = computed(() =>
  logs.filtered({
    robotId: filterRobotId.value || null,
    type: filterType.value || null
  })
)

function formatTime(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => n.toString().padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

function alarmTone(level: AlarmLevel): string {
  switch (level) {
    case '严重':
      return 'danger'
    case '警告':
      return 'warn'
    case '提示':
    default:
      return 'info'
  }
}
function typeTone(t: LogType): string {
  switch (t) {
    case '操作':
      return 'info'
    case '通信':
      return 'info'
    case '报警':
      return 'warn'
    case '系统':
    default:
      return 'offline'
  }
}

async function onClearLogs() {
  try {
    await ElMessageBox.confirm('确认清空全部历史日志?', '清空日志', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning'
    })
    logs.clearLogs()
  } catch {
    // cancel
  }
}

async function onClearAlarms() {
  try {
    await ElMessageBox.confirm('确认清空全部报警记录?', '清空报警', {
      confirmButtonText: '清空',
      cancelButtonText: '取消',
      type: 'warning'
    })
    logs.clearAlarms()
    logs.append('系统', null, '已清空全部报警')
  } catch {
    // cancel
  }
}

function onAckAll() {
  logs.ackAll()
  logs.append('操作', null, '已确认全部当前报警')
}
</script>

<style scoped>
.log-view {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  min-height: 0;
}
.panel {
  padding: 10px 12px;
}
.history {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 8px;
  margin-bottom: 6px;
  gap: 12px;
  flex-wrap: wrap;
}
.header .title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-1);
  font-weight: 600;
}
.header .small {
  font-size: 11.5px;
  font-weight: 400;
}
.actions,
.filters {
  display: flex;
  align-items: center;
  gap: 8px;
}
.logs-table {
  flex: 1;
  min-height: 0;
}
</style>
