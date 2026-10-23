<template>
  <div class="ros-debug-page">
    <aside class="resource-browser panel">
      <div class="browser-header">
        <div>
          <h1>ROS 资源</h1>
          <span>rosapi 响应与标准 Action 话题推断</span>
        </div>
        <el-button
          size="small"
          :disabled="!canRun"
          :loading="discovering"
          @click="discoverResources"
        >
          刷新
        </el-button>
      </div>
      <div class="link-selector">
        <el-select v-model="linkId" filterable placeholder="选择活动 ROS 调试链路">
          <el-option
            v-for="item in rosLinks"
            :key="item.profile.id"
            :label="`${item.profile.displayName} · ${item.profile.driver.toUpperCase()}`"
            :value="item.profile.id"
          />
        </el-select>
        <StatusDot
          :tone="canRun ? 'online' : 'offline'"
          :label="canRun ? '调试通道可用' : '调试通道不可用'"
        />
      </div>
      <el-alert
        class="isolation-notice"
        type="warning"
        :closable="false"
        title="调试消息与正式遥测完全隔离"
      />
      <el-tree
        class="resource-tree"
        :data="resourceTree"
        node-key="key"
        :props="{ label: 'label', children: 'children' }"
        default-expand-all
        highlight-current
        empty-text="选择链路并刷新 ROS 资源"
        @node-click="selectResource"
      >
        <template #default="{ data }">
          <span class="tree-node" :class="{ group: data.group }">
            <el-icon><component :is="resourceIcon(data.type)" /></el-icon>
            <span>{{ data.label }}</span>
            <small v-if="data.children">{{ data.children.length }}</small>
          </span>
        </template>
      </el-tree>
      <div class="browser-footer">
        <el-button size="small" @click="manualResourceVisible = true">手工添加资源</el-button>
      </div>
    </aside>

    <section class="resource-workspace panel">
      <header class="workspace-header">
        <div>
          <span>资源详情</span>
          <h2>{{ selectedResource?.name ?? '未选择资源' }}</h2>
        </div>
        <div class="limits">
          <span>最高 50 条/秒</span>
          <span>单消息 256 KiB</span>
          <el-button size="small" :icon="Download" @click="exportDebugData">导出 JSON</el-button>
        </div>
      </header>

      <div class="workspace-content">
        <section class="resource-detail">
          <div class="detail-grid">
            <div>
              <span>类型</span><b>{{ resourceTypeLabel(selectedResource?.type) }}</b>
            </div>
            <div>
              <span>名称</span><b class="mono">{{ selectedResource?.name ?? '--' }}</b>
            </div>
            <div>
              <span>来源</span><b>{{ selectedResource?.manual ? '手工填写' : 'rosapi / 推断' }}</b>
            </div>
            <div>
              <span>链路</span><b>{{ selectedProfile?.displayName ?? '--' }}</b>
            </div>
          </div>
          <div v-if="selectedResource?.type === 'action'" class="action-hint">
            Action 资源由 <code>/goal</code>、<code>/cancel</code>、<code>/status</code>
            标准话题组推断；也可手工填写。
          </div>
          <div v-if="selectedResource?.type === 'node'" class="node-hint">
            当前接口仅提供节点名发现；节点的发布/订阅关系需目标 rosapi 提供额外接口后才可展示。
          </div>
        </section>

        <section class="operation-editor">
          <div class="editor-heading">
            <b>执行操作</b>
            <StatusBadge
              :label="canRun ? '调试通道已连接' : '不可执行'"
              :tone="canRun ? 'success' : 'warning'"
            />
          </div>
          <div class="editor-controls">
            <el-select v-model="operation" :disabled="!selectedResource">
              <el-option
                v-for="option in operationOptions"
                :key="option.value"
                :label="option.label"
                :value="option.value"
              />
            </el-select>
            <el-input v-model="target" class="mono" placeholder="/resource/name" />
            <label v-if="operation === 'subscribe'">
              限流
              <el-input-number v-model="throttleMs" :min="20" :max="60000" :step="20" />
              ms
            </label>
          </div>
          <div class="json-heading">
            <span>JSON 消息 / 参数 / 服务参数</span>
            <span :class="{ danger: bodySize > maxMessageBytes }">
              {{ formatBytes(bodySize) }} / 256 KiB
            </span>
          </div>
          <el-input
            v-model="jsonBody"
            class="json-editor mono"
            type="textarea"
            :rows="10"
            :disabled="!operationNeedsBody"
          />
          <div class="editor-footer">
            <span>{{ operationHint }}</span>
            <el-button
              type="primary"
              :disabled="!canExecute"
              :loading="running"
              @click="runOperation"
            >
              执行调试操作
            </el-button>
          </div>
        </section>

        <section class="debug-console">
          <el-tabs v-model="consoleTab">
            <el-tab-pane :label="`响应 ${responseEvents.length}`" name="responses">
              <DebugEventList :events="responseEvents" empty-text="尚未收到 rosapi/服务响应" />
            </el-tab-pane>
            <el-tab-pane :label="`订阅消息 ${messageEvents.length}`" name="messages">
              <DebugEventList :events="messageEvents" empty-text="尚未收到调试订阅消息" />
            </el-tab-pane>
            <el-tab-pane :label="`丢弃 ${dropEvents.length}`" name="drops">
              <DebugEventList :events="dropEvents" empty-text="没有因限流或消息大小被丢弃的数据" />
            </el-tab-pane>
            <el-tab-pane label="最近请求" name="request">
              <pre class="single-response">{{ JSON.stringify(lastResponse, null, 2) }}</pre>
            </el-tab-pane>
          </el-tabs>
        </section>
      </div>
    </section>

    <el-dialog v-model="manualResourceVisible" title="手工添加 ROS 资源" width="430px">
      <el-form label-position="top">
        <el-form-item label="资源类型">
          <el-select v-model="manualResource.type">
            <el-option label="节点" value="node" />
            <el-option label="话题" value="topic" />
            <el-option label="服务" value="service" />
            <el-option label="Action" value="action" />
            <el-option label="参数" value="parameter" />
          </el-select>
        </el-form-item>
        <el-form-item label="完整名称">
          <el-input v-model="manualResource.name" class="mono" placeholder="/example/resource" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="manualResourceVisible = false">取消</el-button>
        <el-button type="primary" @click="addManualResource">添加</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, defineComponent, h, reactive, ref, watch } from 'vue'
import { Box, Coin, Connection, Download, List, Monitor, Operation } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { RosDebugRequest } from '@/entities/types'
import { useEventsStore } from '@/entities/events/store'
import { useFleetStore } from '@/entities/fleet/store'
import { api, ApiError } from '@/shared/api/client'
import type { StreamEvent } from '@/shared/api/event-schema'
import StatusBadge from '@/shared/ui/StatusBadge.vue'
import StatusDot from '@/shared/ui/StatusDot.vue'

type ResourceType = 'node' | 'topic' | 'service' | 'action' | 'parameter'

interface ResourceItem {
  key: string
  label: string
  name: string
  type: ResourceType
  manual?: boolean
  group?: boolean
  children?: ResourceItem[]
}

const DebugEventList = defineComponent({
  props: {
    events: { type: Array as () => StreamEvent[], required: true },
    emptyText: { type: String, required: true }
  },
  setup(props) {
    return () =>
      h(
        'div',
        { class: 'debug-event-list' },
        props.events.length
          ? props.events.map((event) =>
              h('article', { key: event.eventId }, [
                h('header', [
                  h('code', event.type),
                  h('time', new Date(event.occurredAt).toLocaleString('zh-CN', { hour12: false }))
                ]),
                h('pre', JSON.stringify(event.payload, null, 2))
              ])
            )
          : [h('div', { class: 'debug-empty' }, props.emptyText)]
      )
  }
})

const fleet = useFleetStore()
const events = useEventsStore()
const linkId = ref('')
const selectedResource = ref<ResourceItem | null>(null)
const manualResources = ref<ResourceItem[]>([])
const manualResourceVisible = ref(false)
const manualResource = reactive<{ type: ResourceType; name: string }>({
  type: 'topic',
  name: ''
})
const operation = ref('subscribe')
const target = ref('')
const jsonBody = ref('{}')
const throttleMs = ref(20)
const discovering = ref(false)
const running = ref(false)
const consoleTab = ref('responses')
const lastResponse = ref<Record<string, unknown> | null>(null)
const maxMessageBytes = 256 * 1024
const rosLinks = computed(() =>
  Object.values(fleet.sessionsByLinkId)
    .map((session) => ({ session, profile: fleet.linksById[session.linkId] }))
    .filter(
      (item) =>
        item.profile &&
        ['ros1', 'ros2'].includes(item.profile.driver) &&
        item.session.debugAvailable
    )
)
const selectedSession = computed(() => fleet.sessionsByLinkId[linkId.value])
const selectedProfile = computed(() => fleet.linksById[linkId.value])
const canRun = computed(() => Boolean(linkId.value && selectedSession.value?.debugAvailable))
const linkDebugEvents = computed(() =>
  events.rosDebugMessages.filter(
    (event) => event.aggregateId === linkId.value || event.payload.linkId === linkId.value
  )
)
const responseEvents = computed(() =>
  linkDebugEvents.value.filter((event) => event.type === 'debug.ros_response')
)
const messageEvents = computed(() =>
  linkDebugEvents.value.filter((event) => event.type === 'debug.ros_message')
)
const dropEvents = computed(() =>
  linkDebugEvents.value.filter((event) => event.type === 'debug.ros_dropped')
)
const discoveredResources = computed(() => {
  const nodes = latestRosapiList('/rosapi/nodes', ['nodes'])
  const topics = latestRosapiList('/rosapi/topics', ['topics'])
  const services = latestRosapiList('/rosapi/services', ['services'])
  const parameters = latestRosapiList('/rosapi/params', ['params', 'parameters'])
  const actionRoots = inferActions(topics)
  return { nodes, topics, services, actions: actionRoots, parameters }
})
const resourceTree = computed<ResourceItem[]>(() => {
  const manualByType = (type: ResourceType) =>
    manualResources.value.filter((resource) => resource.type === type)
  return [
    resourceGroup('节点', 'node', discoveredResources.value.nodes, manualByType('node')),
    resourceGroup('话题', 'topic', discoveredResources.value.topics, manualByType('topic')),
    resourceGroup('服务', 'service', discoveredResources.value.services, manualByType('service')),
    resourceGroup('动作', 'action', discoveredResources.value.actions, manualByType('action')),
    resourceGroup(
      '参数',
      'parameter',
      discoveredResources.value.parameters,
      manualByType('parameter')
    )
  ]
})
const operationOptions = computed(() => {
  const type = selectedResource.value?.type
  if (type === 'topic')
    return [
      { label: '订阅话题', value: 'subscribe' },
      { label: '取消订阅', value: 'unsubscribe' },
      { label: '发布话题', value: 'publish' }
    ]
  if (type === 'service') return [{ label: '调用服务', value: 'call_service' }]
  if (type === 'action')
    return [
      { label: '发送 Goal', value: 'action_goal' },
      { label: '取消 Action', value: 'action_cancel' }
    ]
  if (type === 'parameter')
    return [
      { label: '读取参数', value: 'get_param' },
      { label: '写入参数', value: 'set_param' }
    ]
  return []
})
const operationNeedsBody = computed(
  () => !['subscribe', 'unsubscribe', 'get_param'].includes(operation.value)
)
const bodySize = computed(() => new TextEncoder().encode(jsonBody.value).byteLength)
const canExecute = computed(
  () =>
    canRun.value &&
    Boolean(target.value.trim()) &&
    Boolean(operation.value) &&
    bodySize.value <= maxMessageBytes
)
const operationHint = computed(() => {
  if (!canRun.value) return '请选择活动的 ROS 调试链路'
  if (!selectedResource.value) return '请从左侧选择资源'
  if (bodySize.value > maxMessageBytes) return 'JSON 超过 256 KiB，已禁止发送'
  if (operation.value === 'subscribe')
    return `订阅限流上限 ${Math.round(1000 / throttleMs.value)} 条/秒`
  return '调试请求不会写入正式设备遥测 Store'
})

watch(linkId, () => {
  selectedResource.value = null
  target.value = ''
})
watch(
  rosLinks,
  (available) => {
    if (!available.some((item) => item.profile.id === linkId.value))
      linkId.value = available[0]?.profile.id ?? ''
  },
  { immediate: true }
)

async function discoverResources(): Promise<void> {
  if (!canRun.value) return
  discovering.value = true
  try {
    await Promise.all(
      ['nodes', 'topics', 'services', 'params'].map((nextOperation) =>
        api.rosDebug({
          linkId: linkId.value,
          operation: nextOperation,
          throttleMs: 20,
          message: {},
          arguments: {}
        })
      )
    )
    ElMessage.info('rosapi 发现请求已发送，资源树会随响应更新')
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : 'ROS 资源发现失败')
  } finally {
    discovering.value = false
  }
}

function selectResource(data: ResourceItem): void {
  if (data.group) return
  selectedResource.value = data
  target.value = data.name
  operation.value =
    data.type === 'topic'
      ? 'subscribe'
      : data.type === 'service'
        ? 'call_service'
        : data.type === 'action'
          ? 'action_goal'
          : data.type === 'parameter'
            ? 'get_param'
            : ''
}

async function runOperation(): Promise<void> {
  if (!canExecute.value) return
  let bodyValue: Record<string, unknown> = {}
  if (operationNeedsBody.value) {
    try {
      const parsed: unknown = JSON.parse(jsonBody.value)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed))
        throw new Error('JSON 必须是对象')
      bodyValue = parsed as Record<string, unknown>
    } catch (error) {
      ElMessage.error(error instanceof Error ? error.message : 'JSON 格式无效')
      return
    }
  }
  const request: RosDebugRequest = {
    linkId: linkId.value,
    operation: operation.value,
    throttleMs: throttleMs.value,
    message:
      operation.value === 'publish' ||
      operation.value === 'set_param' ||
      operation.value.startsWith('action_')
        ? bodyValue
        : {},
    arguments: operation.value === 'call_service' ? bodyValue : {}
  }
  if (operation.value === 'call_service') request.service = target.value.trim()
  else if (operation.value.startsWith('action_')) request.action = target.value.trim()
  else if (operation.value === 'get_param' || operation.value === 'set_param')
    request.parameter = target.value.trim()
  else request.topic = target.value.trim()
  running.value = true
  try {
    lastResponse.value = await api.rosDebug(request)
    consoleTab.value = operation.value === 'subscribe' ? 'messages' : 'request'
  } catch (error) {
    ElMessage.error(error instanceof ApiError ? error.message : 'ROS 调试操作失败')
  } finally {
    running.value = false
  }
}

function addManualResource(): void {
  const name = manualResource.name.trim()
  if (!name) {
    ElMessage.warning('请输入 ROS 资源完整名称')
    return
  }
  const item: ResourceItem = {
    key: `manual:${manualResource.type}:${name}`,
    label: name,
    name,
    type: manualResource.type,
    manual: true
  }
  if (!manualResources.value.some((resource) => resource.key === item.key))
    manualResources.value.push(item)
  manualResourceVisible.value = false
  manualResource.name = ''
  selectResource(item)
}

function latestRosapiList(service: string, keys: string[]): string[] {
  for (const event of responseEvents.value) {
    const response = event.payload.response
    if (!response || typeof response !== 'object') continue
    const record = response as Record<string, unknown>
    if (record.service !== service) continue
    const values =
      record.values && typeof record.values === 'object'
        ? (record.values as Record<string, unknown>)
        : record
    for (const key of keys) {
      const list = values[key]
      if (Array.isArray(list))
        return [...new Set(list.filter((item): item is string => typeof item === 'string'))].sort()
    }
  }
  return []
}

function inferActions(topics: string[]): string[] {
  const suffixes = ['/goal', '/cancel', '/status']
  const groups = new Map<string, Set<string>>()
  for (const topic of topics) {
    const suffix = suffixes.find((candidate) => topic.endsWith(candidate))
    if (!suffix) continue
    const root = topic.slice(0, -suffix.length)
    const found = groups.get(root) ?? new Set<string>()
    found.add(suffix)
    groups.set(root, found)
  }
  return [...groups.entries()]
    .filter(([, suffixSet]) => suffixSet.has('/goal') && suffixSet.has('/status'))
    .map(([root]) => root)
    .sort()
}

function resourceGroup(
  label: string,
  type: ResourceType,
  discovered: string[],
  manual: ResourceItem[]
): ResourceItem {
  const children = [
    ...discovered.map((name) => ({
      key: `${type}:${name}`,
      label: name,
      name,
      type
    })),
    ...manual
  ]
  return {
    key: `group:${type}`,
    label,
    name: label,
    type,
    group: true,
    children
  }
}

function resourceIcon(type: ResourceType): object {
  return (
    {
      node: Monitor,
      topic: List,
      service: Connection,
      action: Operation,
      parameter: Coin
    }[type] ?? Box
  )
}

function resourceTypeLabel(type: ResourceType | undefined): string {
  return type
    ? { node: '节点', topic: '话题', service: '服务', action: 'Action', parameter: '参数' }[type]
    : '--'
}

function exportDebugData(): void {
  const data = {
    exportedAt: new Date().toISOString(),
    linkId: linkId.value,
    resource: selectedResource.value,
    lastResponse: lastResponse.value,
    events: linkDebugEvents.value
  }
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  )
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `polarmarine-ros-debug-${Date.now()}.json`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

function formatBytes(bytes: number): string {
  return bytes < 1024 ? `${bytes} B` : `${(bytes / 1024).toFixed(1)} KiB`
}
</script>

<style scoped>
.ros-debug-page {
  display: grid;
  grid-template-columns: 300px minmax(620px, 1fr);
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.resource-browser,
.resource-workspace {
  min-height: 0;
  overflow: hidden;
}

.resource-browser {
  display: flex;
  flex-direction: column;
}

.browser-header,
.workspace-header,
.limits,
.editor-heading,
.editor-footer,
.json-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.browser-header {
  padding: 10px 12px;
  border-bottom: 1px solid var(--border);
}

h1,
h2 {
  margin: 0;
  font-size: 14px;
}

.browser-header span,
.workspace-header span {
  display: block;
  margin-top: 2px;
  color: var(--text-3);
  font-size: 9.5px;
}

.link-selector {
  display: flex;
  flex-direction: column;
  gap: 7px;
  padding: 10px;
}

.isolation-notice {
  margin: 0 10px 8px;
}

.resource-tree {
  flex: 1;
  min-height: 0;
  padding: 2px 8px 8px;
  overflow-y: auto;
  background: transparent;
}

.resource-tree :deep(.el-tree-node__content) {
  min-height: 30px;
  color: var(--text-2);
}

.resource-tree :deep(.el-tree-node__content:hover),
.resource-tree :deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: var(--bg-hover);
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 7px;
  min-width: 0;
}

.tree-node > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tree-node small {
  padding: 1px 5px;
  color: var(--text-3);
  border-radius: 999px;
  background: var(--bg-panel-2);
  font-size: 9px;
}

.tree-node.group {
  color: var(--text-1);
  font-weight: 600;
}

.browser-footer {
  padding: 8px 10px;
  border-top: 1px solid var(--border);
}

.browser-footer .el-button {
  width: 100%;
}

.resource-workspace {
  display: flex;
  flex-direction: column;
}

.workspace-header {
  flex: 0 0 54px;
  min-height: 54px;
  padding: 8px 12px;
  border-bottom: 1px solid var(--border);
}

.workspace-header h2 {
  margin-top: 2px;
  font-size: 15px;
}

.limits {
  color: var(--text-3);
  font-size: 10.5px;
}

.workspace-content {
  display: grid;
  grid-template-rows: auto auto minmax(220px, 1fr);
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.resource-detail,
.operation-editor {
  padding: 11px 13px;
  border-bottom: 1px solid var(--border);
}

.detail-grid {
  display: grid;
  grid-template-columns: 110px minmax(180px, 1fr) 120px minmax(150px, 0.8fr);
  gap: 10px;
}

.detail-grid div {
  display: flex;
  flex-direction: column;
  min-width: 0;
  gap: 3px;
}

.detail-grid span {
  color: var(--text-3);
  font-size: 9.5px;
}

.detail-grid b {
  overflow: hidden;
  color: var(--text-1);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.action-hint,
.node-hint {
  margin-top: 9px;
  color: var(--text-3);
  font-size: 10.5px;
}

.editor-heading {
  margin-bottom: 9px;
}

.editor-controls {
  display: grid;
  grid-template-columns: 180px minmax(240px, 1fr) auto;
  gap: 8px;
}

.editor-controls label {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-3);
  font-size: 10px;
}

.editor-controls label .el-input-number {
  width: 112px;
}

.json-heading {
  margin: 9px 0 5px;
  color: var(--text-3);
  font-size: 10px;
}

.json-heading .danger {
  color: var(--color-danger);
}

.json-editor :deep(.el-textarea__inner) {
  line-height: 1.5;
}

.editor-footer {
  margin-top: 8px;
}

.editor-footer span {
  color: var(--text-3);
  font-size: 10.5px;
}

.debug-console {
  min-height: 0;
  padding: 0 12px 10px;
  overflow: hidden;
}

.debug-console :deep(.el-tabs) {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.debug-console :deep(.el-tabs__header) {
  flex: 0 0 auto;
  margin-bottom: 6px;
}

.debug-console :deep(.el-tabs__content),
.debug-console :deep(.el-tab-pane) {
  height: 100%;
  min-height: 0;
}

.debug-console :deep(.el-tabs__content) {
  flex: 1;
}

.single-response {
  height: 100%;
  margin: 0;
  padding: 10px;
  overflow: auto;
  color: var(--text-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--code-bg);
}

:deep(.debug-event-list) {
  height: 100%;
  overflow-y: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--code-bg);
}

:deep(.debug-event-list article) {
  padding: 8px 10px;
  border-bottom: 1px solid var(--border);
}

:deep(.debug-event-list header) {
  display: flex;
  justify-content: space-between;
}

:deep(.debug-event-list code) {
  color: var(--color-accent);
}

:deep(.debug-event-list time) {
  color: var(--text-muted);
  font-size: 9px;
}

:deep(.debug-event-list pre) {
  margin: 5px 0 0;
  color: var(--text-2);
  font-size: 10px;
  white-space: pre-wrap;
}

:deep(.debug-empty) {
  display: grid;
  height: 100%;
  place-items: center;
  color: var(--text-muted);
}

:deep(.el-select) {
  width: 100%;
}

@media (width <= 1450px) {
  .ros-debug-page {
    grid-template-columns: 260px minmax(590px, 1fr);
  }
}
</style>
