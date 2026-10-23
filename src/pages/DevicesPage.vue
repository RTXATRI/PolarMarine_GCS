<template>
  <div class="devices-page">
    <aside class="master-panel panel">
      <div class="master-header">
        <div>
          <h1>设备管理</h1>
          <span
            >配置 {{ fleet.devices.length }} / {{ application.settings.maxConfiguredDevices }}</span
          >
        </div>
        <el-button
          type="primary"
          size="small"
          :disabled="fleet.devices.length >= application.settings.maxConfiguredDevices"
          @click="openDeviceEditor()"
        >
          新增
        </el-button>
      </div>
      <el-input v-model="search" class="search" clearable placeholder="搜索设备、ID 或标签">
        <template #prefix
          ><el-icon><Search /></el-icon
        ></template>
      </el-input>
      <div class="device-list">
        <button
          v-for="device in filteredDevices"
          :key="device.id"
          class="device-item"
          :class="{ selected: device.id === fleet.selectedDeviceId }"
          type="button"
          @click="fleet.selectDevice(device.id)"
        >
          <span class="device-icon"
            ><el-icon><Monitor /></el-icon
          ></span>
          <span class="device-copy">
            <b>{{ device.displayName }}</b>
            <small class="mono">{{ device.id }}</small>
          </span>
          <StatusDot
            :tone="operationTone(fleet.operationsByDeviceId[device.id]?.status)"
            :label="operationText(fleet.operationsByDeviceId[device.id]?.status)"
          />
        </button>
        <div v-if="!filteredDevices.length" class="empty-list">没有匹配的设备</div>
      </div>
      <div class="master-footer">
        <el-button size="small" @click="openTemplateEditor()">新增模板</el-button>
        <el-button size="small" @click="templateManagerVisible = true">模板列表</el-button>
      </div>
    </aside>

    <section class="detail-panel panel">
      <div v-if="!fleet.selectedDevice" class="page-empty">请选择或新增设备</div>
      <template v-else>
        <header class="detail-header">
          <div>
            <div class="heading-line">
              <h2>{{ fleet.selectedDevice.displayName }}</h2>
              <StatusDot
                :tone="operationTone(fleet.selectedOperationalState?.status)"
                :label="operationText(fleet.selectedOperationalState?.status)"
              />
            </div>
            <p class="mono">{{ fleet.selectedDevice.id }}</p>
          </div>
          <div>
            <el-button size="small" @click="openDeviceEditor(fleet.selectedDevice)"
              >编辑档案</el-button
            >
            <el-button size="small" type="danger" plain @click="removeDevice(fleet.selectedDevice)">
              删除设备
            </el-button>
          </div>
        </header>

        <el-tabs v-model="activeDetailTab" class="detail-tabs">
          <el-tab-pane label="档案" name="profile">
            <div class="profile-grid">
              <section class="info-card">
                <h3>设备档案</h3>
                <dl>
                  <div>
                    <dt>显示名称</dt>
                    <dd>{{ fleet.selectedDevice.displayName }}</dd>
                  </div>
                  <div>
                    <dt>稳定 ID</dt>
                    <dd class="mono">{{ fleet.selectedDevice.id }}</dd>
                  </div>
                  <div>
                    <dt>设备模板</dt>
                    <dd>
                      {{ fleet.selectedTemplate?.displayName ?? fleet.selectedDevice.templateId }}
                    </dd>
                  </div>
                  <div>
                    <dt>设备类别</dt>
                    <dd>{{ categoryLabel(fleet.selectedTemplate?.category) }}</dd>
                  </div>
                  <div>
                    <dt>是否启用</dt>
                    <dd>{{ fleet.selectedDevice.enabled ? '启用' : '停用' }}</dd>
                  </div>
                  <div>
                    <dt>说明</dt>
                    <dd>{{ fleet.selectedDevice.description || '无' }}</dd>
                  </div>
                </dl>
              </section>
              <section class="info-card">
                <h3>运行摘要</h3>
                <dl>
                  <div>
                    <dt>聚合状态</dt>
                    <dd>{{ operationText(fleet.selectedOperationalState?.status) }}</dd>
                  </div>
                  <div>
                    <dt>活动路由</dt>
                    <dd class="mono">
                      {{
                        fleet.selectedOperationalState?.activeLinkId
                          ? (fleet.linksById[fleet.selectedOperationalState.activeLinkId]
                              ?.displayName ?? fleet.selectedOperationalState.activeLinkId)
                          : '--'
                      }}
                    </dd>
                  </div>
                  <div>
                    <dt>健康链路</dt>
                    <dd>{{ fleet.selectedOperationalState?.healthyLinkIds.length ?? 0 }}</dd>
                  </div>
                  <div>
                    <dt>最近故障切换</dt>
                    <dd>{{ formatTime(fleet.selectedOperationalState?.lastFailoverAt) }}</dd>
                  </div>
                  <div>
                    <dt>标签</dt>
                    <dd>{{ fleet.selectedDevice.tags?.join('、') || '无' }}</dd>
                  </div>
                </dl>
              </section>
            </div>
          </el-tab-pane>

          <el-tab-pane label="链路" name="links">
            <div class="link-host"><LinkManager /></div>
          </el-tab-pane>

          <el-tab-pane label="模板能力" name="template">
            <div class="template-toolbar">
              <div>
                <b>{{ fleet.selectedTemplate?.displayName ?? '--' }}</b>
                <span>{{ fleet.selectedTemplate?.description || '模板未填写说明' }}</span>
              </div>
              <el-button
                size="small"
                type="primary"
                plain
                :disabled="!fleet.selectedTemplate"
                @click="openTemplateEditor(fleet.selectedTemplate ?? undefined)"
              >
                编辑模板
              </el-button>
            </div>
            <div class="capability-summary">
              <section class="info-card">
                <h3>能力声明</h3>
                <div class="capability-tags">
                  <el-tag
                    v-for="capability in fleet.selectedTemplate?.capabilities ?? []"
                    :key="capability"
                    size="small"
                    effect="plain"
                  >
                    {{ capability }}
                  </el-tag>
                  <span v-if="!fleet.selectedTemplate?.capabilities?.length" class="muted">无</span>
                </div>
              </section>
              <section class="info-card">
                <h3>逻辑媒体通道</h3>
                <el-table :data="fleet.selectedTemplate?.mediaChannels ?? []" size="small">
                  <el-table-column prop="displayName" label="名称" min-width="120" />
                  <el-table-column prop="id" label="通道 ID" min-width="120" />
                  <el-table-column prop="role" label="角色" width="90" />
                  <el-table-column label="必需" width="70">
                    <template #default="{ row }">{{ row.required ? '是' : '否' }}</template>
                  </el-table-column>
                </el-table>
              </section>
              <section class="info-card parameter-card">
                <h3>参数元数据</h3>
                <el-table :data="fleet.selectedTemplate?.parameters ?? []" size="small">
                  <el-table-column prop="displayName" label="名称" min-width="130" />
                  <el-table-column prop="key" label="键" min-width="150" />
                  <el-table-column prop="valueType" label="类型" width="90" />
                  <el-table-column prop="unit" label="单位" width="70" />
                  <el-table-column label="范围" min-width="120">
                    <template #default="{ row }">{{ parameterRange(row) }}</template>
                  </el-table-column>
                  <el-table-column prop="description" label="说明" min-width="180" />
                </el-table>
              </section>
            </div>
          </el-tab-pane>
        </el-tabs>
      </template>
    </section>

    <el-dialog
      v-model="deviceEditorVisible"
      :title="editingDeviceId ? '编辑设备档案' : '新增设备'"
      width="560px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="稳定 ID">
          <el-input
            v-model="deviceForm.id"
            :disabled="Boolean(editingDeviceId)"
            placeholder="例如 survey-usv-01"
          />
        </el-form-item>
        <el-form-item label="设备模板">
          <el-select v-model="deviceForm.templateId" filterable>
            <el-option
              v-for="template in fleet.templates"
              :key="template.id"
              :label="`${template.displayName} · ${template.id}`"
              :value="template.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名称"><el-input v-model="deviceForm.displayName" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="deviceForm.description" /></el-form-item>
        <el-form-item label="标签（逗号分隔）"><el-input v-model="deviceForm.tags" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="deviceForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deviceEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingDevice" @click="saveDevice">保存档案</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="templateManagerVisible" title="设备模板" size="720px">
      <div class="template-list-toolbar">
        <span>模板用于声明能力、参数和逻辑媒体通道。</span>
        <el-button type="primary" size="small" @click="openTemplateEditor()">新增模板</el-button>
      </div>
      <el-table :data="fleet.templates">
        <el-table-column prop="displayName" label="名称" min-width="130" />
        <el-table-column prop="id" label="稳定 ID" min-width="180" />
        <el-table-column label="类别" width="90">
          <template #default="{ row }">{{ categoryLabel(row.category) }}</template>
        </el-table-column>
        <el-table-column label="能力" width="80">
          <template #default="{ row }">{{ row.capabilities?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openTemplateEditor(row)">编辑</el-button>
            <el-button link type="danger" @click="removeTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>

    <el-dialog
      v-model="templateEditorVisible"
      :title="editingTemplateId ? '编辑设备模板' : '新增设备模板'"
      width="920px"
      top="4vh"
      destroy-on-close
    >
      <el-tabs v-model="templateEditorTab" @tab-change="onTemplateTabChange">
        <el-tab-pane label="结构化编辑" name="structured">
          <div class="template-form-scroll">
            <el-form label-position="top">
              <div class="form-grid three">
                <el-form-item label="稳定 ID">
                  <el-input
                    v-model="templateDraft.id"
                    :disabled="Boolean(editingTemplateId)"
                    placeholder="polarmarine.usv.inspection"
                  />
                </el-form-item>
                <el-form-item label="显示名称">
                  <el-input v-model="templateDraft.displayName" />
                </el-form-item>
                <el-form-item label="类别">
                  <el-select v-model="templateDraft.category">
                    <el-option label="无人机" value="aerial" />
                    <el-option label="无人船" value="surface" />
                    <el-option label="固定站" value="station" />
                    <el-option label="通用设备" value="generic" />
                  </el-select>
                </el-form-item>
              </div>
              <el-form-item label="说明"
                ><el-input v-model="templateDraft.description"
              /></el-form-item>
            </el-form>

            <section class="editor-section">
              <div class="editor-title">
                <div><b>能力分组</b><span>设备握手结果会与这里的声明取交集。</span></div>
              </div>
              <div class="capability-groups">
                <div v-for="group in capabilityGroups" :key="group.label" class="capability-group">
                  <strong>{{ group.label }}</strong>
                  <el-checkbox-group v-model="templateDraft.capabilities">
                    <el-checkbox v-for="item in group.items" :key="item.value" :value="item.value">
                      {{ item.label }}
                      <small class="mono">{{ item.value }}</small>
                    </el-checkbox>
                  </el-checkbox-group>
                </div>
              </div>
              <div class="extension-capabilities">
                <span>扩展能力</span>
                <el-tag
                  v-for="capability in extensionCapabilities"
                  :key="capability"
                  closable
                  effect="plain"
                  @close="removeExtensionCapability(capability)"
                >
                  {{ capability }}
                </el-tag>
                <el-input
                  v-model="newCapability"
                  size="small"
                  placeholder="输入未知/自定义能力代码"
                  @keyup.enter="addExtensionCapability"
                >
                  <template #append
                    ><el-button @click="addExtensionCapability">添加</el-button></template
                  >
                </el-input>
              </div>
            </section>

            <section class="editor-section">
              <div class="editor-title">
                <div><b>参数元数据</b><span>驱动参数页将按这些约束生成控件和校验。</span></div>
                <el-button size="small" @click="addParameter">新增参数</el-button>
              </div>
              <el-table :data="templateDraft.parameters" size="small" max-height="240">
                <el-table-column label="键" min-width="150">
                  <template #default="{ row }"
                    ><el-input v-model="row.key" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="显示名称" min-width="130">
                  <template #default="{ row }"
                    ><el-input v-model="row.displayName" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="类型" width="105">
                  <template #default="{ row }">
                    <el-select v-model="row.valueType" size="small">
                      <el-option label="数值" value="number" />
                      <el-option label="整数" value="integer" />
                      <el-option label="布尔" value="boolean" />
                      <el-option label="文本" value="string" />
                      <el-option label="枚举" value="enum" />
                    </el-select>
                  </template>
                </el-table-column>
                <el-table-column label="默认值" min-width="100">
                  <template #default="{ row }"
                    ><el-input v-model="row.defaultValue" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="单位" width="78">
                  <template #default="{ row }"
                    ><el-input v-model="row.unit" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="最小" width="78">
                  <template #default="{ row }"
                    ><el-input v-model="row.minimum" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="最大" width="78">
                  <template #default="{ row }"
                    ><el-input v-model="row.maximum" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="枚举值（逗号）" min-width="130">
                  <template #default="{ row }"
                    ><el-input v-model="row.enumValues" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="" width="55" fixed="right">
                  <template #default="{ $index }">
                    <el-button
                      link
                      type="danger"
                      @click="templateDraft.parameters.splice($index, 1)"
                      >删</el-button
                    >
                  </template>
                </el-table-column>
              </el-table>
            </section>

            <section class="editor-section">
              <div class="editor-title">
                <div><b>逻辑媒体通道</b><span>本机 UVC 设备绑定不会写入后端。</span></div>
                <el-button size="small" @click="addMediaChannel">新增通道</el-button>
              </div>
              <el-table :data="templateDraft.mediaChannels" size="small" max-height="190">
                <el-table-column label="通道 ID" min-width="140">
                  <template #default="{ row }"><el-input v-model="row.id" size="small" /></template>
                </el-table-column>
                <el-table-column label="显示名称" min-width="140">
                  <template #default="{ row }"
                    ><el-input v-model="row.displayName" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="角色" min-width="120">
                  <template #default="{ row }"
                    ><el-input v-model="row.role" size="small"
                  /></template>
                </el-table-column>
                <el-table-column label="必需" width="80">
                  <template #default="{ row }"><el-switch v-model="row.required" /></template>
                </el-table-column>
                <el-table-column label="" width="55">
                  <template #default="{ $index }">
                    <el-button
                      link
                      type="danger"
                      @click="templateDraft.mediaChannels.splice($index, 1)"
                      >删</el-button
                    >
                  </template>
                </el-table-column>
              </el-table>
            </section>
          </div>
        </el-tab-pane>
        <el-tab-pane label="高级 JSON" name="json">
          <el-alert
            type="warning"
            :closable="false"
            title="切回结构化编辑时会进行运行时 Schema 校验；未知能力代码会原样保留。"
          />
          <el-input v-model="advancedJson" class="advanced-json mono" type="textarea" :rows="27" />
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="templateEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingTemplate" @click="saveTemplate"
          >保存模板</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import { Monitor, Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { z } from 'zod'
import type { Device, DeviceTemplate, DeviceTemplateWrite, DeviceWrite } from '@/entities/types'
import { useApplicationStore } from '@/app/store'
import { useFleetStore } from '@/entities/fleet/store'
import LinkManager from '@/features/links/LinkManager.vue'
import { api, ApiError } from '@/shared/api/client'
import { refreshServerState } from '@/shared/api/data-source'
import {
  categoryLabel,
  deviceSearchText,
  operationText,
  operationTone
} from '@/shared/lib/device-view'
import { formatTime } from '@/shared/lib/presentation'
import StatusDot from '@/shared/ui/StatusDot.vue'

type ParameterDefinition = NonNullable<DeviceTemplateWrite['parameters']>[number]
type MediaChannel = NonNullable<DeviceTemplateWrite['mediaChannels']>[number]
type ParameterValueType = ParameterDefinition['valueType']

interface ParameterDraft {
  key: string
  displayName: string
  valueType: ParameterValueType
  defaultValue: string
  unit: string
  minimum: string
  maximum: string
  step: string
  description: string
  enumValues: string
  readOnly: boolean
}

interface TemplateDraft {
  id: string
  displayName: string
  category: DeviceTemplateWrite['category']
  description: string
  capabilities: string[]
  parameters: ParameterDraft[]
  mediaChannels: MediaChannel[]
}

const parameterSchema = z.object({
  key: z.string().min(1),
  displayName: z.string().min(1),
  valueType: z.enum(['number', 'integer', 'boolean', 'string', 'enum']),
  defaultValue: z.unknown(),
  unit: z.string().nullable().optional(),
  minimum: z.number().nullable().optional(),
  maximum: z.number().nullable().optional(),
  step: z.number().nullable().optional(),
  description: z.string(),
  enumValues: z.array(z.string()).optional(),
  readOnly: z.boolean()
})
const mediaChannelSchema = z.object({
  id: z.string().min(1),
  displayName: z.string().min(1),
  role: z.string(),
  required: z.boolean()
})
const templateWriteSchema = z.object({
  id: z.string().min(1).nullable().optional(),
  displayName: z.string().min(1),
  category: z.enum(['aerial', 'surface', 'station', 'generic']),
  description: z.string(),
  capabilities: z.array(z.string()).optional(),
  parameters: z.array(parameterSchema).optional(),
  mediaChannels: z.array(mediaChannelSchema).optional()
})

const capabilityGroups = [
  {
    label: '遥测',
    items: [
      { value: 'telemetry.read', label: '读取遥测' },
      { value: 'telemetry.position', label: '定位' },
      { value: 'telemetry.battery', label: '电池' }
    ]
  },
  {
    label: '控制',
    items: [
      { value: 'command.manual_control', label: '手动控制' },
      { value: 'command.mode_control', label: '模式切换' },
      { value: 'command.arm', label: '解锁/上锁' },
      { value: 'command.emergency_stop', label: '全链路急停' }
    ]
  },
  {
    label: '任务',
    items: [
      { value: 'mission.waypoint', label: '目标点' },
      { value: 'mission.route', label: '路线' },
      { value: 'mission.return_home', label: '返航' }
    ]
  },
  {
    label: '参数与媒体',
    items: [
      { value: 'parameters.read', label: '参数读取' },
      { value: 'parameters.write', label: '参数写入' },
      { value: 'parameters.persist', label: '保存到设备' },
      { value: 'media.uvc', label: '本机 UVC' }
    ]
  },
  {
    label: '作业扩展',
    items: [
      { value: 'dock.charge', label: '返航充电' },
      { value: 'payload.waste_collection', label: '垃圾收集' },
      { value: 'payload.electromagnetic_fix', label: '电磁固定' }
    ]
  }
] as const
const knownCapabilities = new Set<string>(
  capabilityGroups.flatMap((group) => group.items.map((item) => item.value))
)

const fleet = useFleetStore()
const application = useApplicationStore()
const search = ref('')
const activeDetailTab = ref('profile')
const deviceEditorVisible = ref(false)
const templateEditorVisible = ref(false)
const templateManagerVisible = ref(false)
const templateEditorTab = ref<'structured' | 'json'>('structured')
const editingDeviceId = ref<string | null>(null)
const editingTemplateId = ref<string | null>(null)
const savingDevice = ref(false)
const savingTemplate = ref(false)
const newCapability = ref('')
const advancedJson = ref('')
const deviceForm = reactive({
  id: '',
  templateId: '',
  displayName: '',
  description: '',
  tags: '',
  enabled: true
})
const templateDraft = reactive<TemplateDraft>(emptyTemplateDraft())
const filteredDevices = computed(() => {
  const query = search.value.trim().toLocaleLowerCase('zh-CN')
  return [...fleet.devices]
    .filter(
      (device) =>
        !query || deviceSearchText(device, fleet.templatesById[device.templateId]).includes(query)
    )
    .sort((left, right) => left.displayName.localeCompare(right.displayName, 'zh-CN'))
})
const extensionCapabilities = computed(() =>
  templateDraft.capabilities.filter((capability) => !knownCapabilities.has(capability))
)

function openDeviceEditor(device?: Device): void {
  editingDeviceId.value = device?.id ?? null
  Object.assign(deviceForm, {
    id: device?.id ?? '',
    templateId: device?.templateId ?? fleet.templates[0]?.id ?? '',
    displayName: device?.displayName ?? '',
    description: device?.description ?? '',
    tags: device?.tags?.join(', ') ?? '',
    enabled: device?.enabled ?? true
  })
  deviceEditorVisible.value = true
}

async function saveDevice(): Promise<void> {
  if (!deviceForm.id.trim() || !deviceForm.templateId || !deviceForm.displayName.trim()) {
    ElMessage.error('请填写稳定 ID、设备模板和显示名称')
    return
  }
  const body: DeviceWrite = {
    id: deviceForm.id.trim(),
    templateId: deviceForm.templateId,
    displayName: deviceForm.displayName.trim(),
    enabled: deviceForm.enabled,
    description: deviceForm.description.trim(),
    tags: deviceForm.tags
      .split(',')
      .map((tag) => tag.trim())
      .filter(Boolean)
  }
  savingDevice.value = true
  try {
    const saved = editingDeviceId.value
      ? await api.updateDevice(editingDeviceId.value, body)
      : await api.createDevice(body)
    await refreshServerState()
    fleet.selectDevice(saved.id)
    deviceEditorVisible.value = false
    ElMessage.success('设备档案已保存；连接运行态未改变')
  } catch (error) {
    showError(error, '设备保存失败')
  } finally {
    savingDevice.value = false
  }
}

async function removeDevice(device: Device): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除设备档案“${device.displayName}”？所有链路必须处于停止状态。`,
      '删除设备',
      { type: 'warning' }
    )
    await api.deleteDevice(device.id)
    await refreshServerState()
    ElMessage.success('设备档案已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') showError(error, '设备删除失败')
  }
}

function openTemplateEditor(template?: DeviceTemplate): void {
  editingTemplateId.value = template?.id ?? null
  loadStructuredDraft(
    template
      ? {
          id: template.id,
          displayName: template.displayName,
          category: template.category,
          description: template.description,
          capabilities: [...(template.capabilities ?? [])],
          parameters: [...(template.parameters ?? [])],
          mediaChannels: [...(template.mediaChannels ?? [])]
        }
      : {
          id: '',
          displayName: '',
          category: 'generic',
          description: '',
          capabilities: [],
          parameters: [],
          mediaChannels: []
        }
  )
  advancedJson.value = JSON.stringify(buildTemplateBody(), null, 2)
  templateEditorTab.value = 'structured'
  templateEditorVisible.value = true
}

function onTemplateTabChange(name: string | number): void {
  if (name === 'json') {
    try {
      advancedJson.value = JSON.stringify(buildTemplateBody(), null, 2)
    } catch (error) {
      templateEditorTab.value = 'structured'
      showError(error, '结构化表单存在无效值')
    }
    return
  }
  try {
    loadStructuredDraft(parseAdvancedJson())
  } catch (error) {
    templateEditorTab.value = 'json'
    showError(error, '高级 JSON 未通过 Schema 校验')
  }
}

async function saveTemplate(): Promise<void> {
  try {
    const body = templateEditorTab.value === 'json' ? parseAdvancedJson() : buildTemplateBody()
    savingTemplate.value = true
    const saved = editingTemplateId.value
      ? await api.updateTemplate(editingTemplateId.value, body)
      : await api.createTemplate(body)
    await refreshServerState()
    templateEditorVisible.value = false
    templateManagerVisible.value = false
    if (fleet.selectedDevice?.templateId === saved.id) activeDetailTab.value = 'template'
    ElMessage.success('设备模板已保存')
  } catch (error) {
    showError(error, '模板保存失败')
  } finally {
    savingTemplate.value = false
  }
}

async function removeTemplate(template: DeviceTemplate): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `确定删除模板“${template.displayName}”？仍被设备引用时后端会拒绝。`,
      '删除模板',
      { type: 'warning' }
    )
    await api.deleteTemplate(template.id)
    await refreshServerState()
    ElMessage.success('设备模板已删除')
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') showError(error, '模板删除失败')
  }
}

function buildTemplateBody(): DeviceTemplateWrite {
  const body: DeviceTemplateWrite = {
    id: templateDraft.id.trim(),
    displayName: templateDraft.displayName.trim(),
    category: templateDraft.category,
    description: templateDraft.description.trim(),
    capabilities: [
      ...new Set(templateDraft.capabilities.map((value) => value.trim()).filter(Boolean))
    ],
    parameters: templateDraft.parameters.map(parameterFromDraft),
    mediaChannels: templateDraft.mediaChannels.map((channel) => ({
      id: channel.id.trim(),
      displayName: channel.displayName.trim(),
      role: channel.role.trim() || 'video',
      required: channel.required
    }))
  }
  return templateWriteSchema.parse(body) as DeviceTemplateWrite
}

function parseAdvancedJson(): DeviceTemplateWrite {
  return templateWriteSchema.parse(JSON.parse(advancedJson.value)) as DeviceTemplateWrite
}

function loadStructuredDraft(body: DeviceTemplateWrite): void {
  Object.assign(templateDraft, {
    id: body.id ?? '',
    displayName: body.displayName,
    category: body.category,
    description: body.description,
    capabilities: [...(body.capabilities ?? [])],
    parameters: (body.parameters ?? []).map(parameterToDraft),
    mediaChannels: (body.mediaChannels ?? []).map((channel) => ({ ...channel }))
  })
}

function emptyTemplateDraft(): TemplateDraft {
  return {
    id: '',
    displayName: '',
    category: 'generic',
    description: '',
    capabilities: [],
    parameters: [],
    mediaChannels: []
  }
}

function parameterToDraft(parameter: ParameterDefinition): ParameterDraft {
  return {
    key: parameter.key,
    displayName: parameter.displayName,
    valueType: parameter.valueType,
    defaultValue: JSON.stringify(parameter.defaultValue),
    unit: parameter.unit ?? '',
    minimum: parameter.minimum == null ? '' : String(parameter.minimum),
    maximum: parameter.maximum == null ? '' : String(parameter.maximum),
    step: parameter.step == null ? '' : String(parameter.step),
    description: parameter.description,
    enumValues: parameter.enumValues?.join(', ') ?? '',
    readOnly: parameter.readOnly
  }
}

function parameterFromDraft(parameter: ParameterDraft): ParameterDefinition {
  return parameterSchema.parse({
    key: parameter.key.trim(),
    displayName: parameter.displayName.trim(),
    valueType: parameter.valueType,
    defaultValue: parseDefaultValue(parameter.defaultValue),
    unit: parameter.unit.trim() || null,
    minimum: optionalNumber(parameter.minimum),
    maximum: optionalNumber(parameter.maximum),
    step: optionalNumber(parameter.step),
    description: parameter.description.trim(),
    enumValues: parameter.enumValues
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean),
    readOnly: parameter.readOnly
  }) as ParameterDefinition
}

function addParameter(): void {
  templateDraft.parameters.push({
    key: '',
    displayName: '',
    valueType: 'number',
    defaultValue: '0',
    unit: '',
    minimum: '',
    maximum: '',
    step: '',
    description: '',
    enumValues: '',
    readOnly: false
  })
}

function addMediaChannel(): void {
  const index = templateDraft.mediaChannels.length + 1
  templateDraft.mediaChannels.push({
    id: `camera-${index}`,
    displayName: `CAM-${index}`,
    role: 'video',
    required: false
  })
}

function addExtensionCapability(): void {
  const value = newCapability.value.trim()
  if (value && !templateDraft.capabilities.includes(value)) templateDraft.capabilities.push(value)
  newCapability.value = ''
}

function removeExtensionCapability(capability: string): void {
  templateDraft.capabilities = templateDraft.capabilities.filter((item) => item !== capability)
}

function parseDefaultValue(value: string): unknown {
  try {
    return JSON.parse(value)
  } catch {
    return value
  }
}

function optionalNumber(value: string): number | null {
  if (!value.trim()) return null
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) throw new Error(`“${value}”不是有效数字`)
  return parsed
}

function parameterRange(parameter: ParameterDefinition): string {
  if (parameter.enumValues?.length) return parameter.enumValues.join(' / ')
  if (parameter.minimum == null && parameter.maximum == null) return '--'
  return `${parameter.minimum ?? '−∞'} ～ ${parameter.maximum ?? '+∞'}`
}

function showError(error: unknown, fallback: string): void {
  if (error instanceof z.ZodError) {
    ElMessage.error(
      `${fallback}：${error.issues[0]?.path.join('.') || 'root'} ${error.issues[0]?.message}`
    )
    return
  }
  ElMessage.error(error instanceof ApiError || error instanceof Error ? error.message : fallback)
}
</script>

<style scoped>
.devices-page {
  display: grid;
  grid-template-columns: 300px minmax(620px, 1fr);
  gap: 12px;
  height: 100%;
  min-height: 0;
}

.master-panel,
.detail-panel {
  min-height: 0;
  overflow: hidden;
}

.master-panel {
  display: flex;
  flex-direction: column;
}

.master-header,
.detail-header,
.template-toolbar,
.template-list-toolbar,
.editor-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.master-header {
  padding: 13px 14px 10px;
}

h1,
h2,
h3,
p {
  margin: 0;
}

h1 {
  font-size: 15px;
}

.master-header span,
.template-list-toolbar span,
.editor-title span {
  display: block;
  margin-top: 3px;
  color: var(--text-3);
  font-size: 10.5px;
}

.search {
  width: auto;
  margin: 0 10px 9px;
}

.device-list {
  display: flex;
  flex: 1;
  flex-direction: column;
  gap: 5px;
  min-height: 0;
  padding: 0 8px 8px;
  overflow-y: auto;
}

.device-item {
  display: grid;
  grid-template-columns: 32px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  width: 100%;
  padding: 9px;
  color: var(--text-1);
  text-align: left;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  background: transparent;
  cursor: pointer;
}

.device-item:hover {
  background: var(--bg-hover);
}

.device-item.selected {
  border-color: var(--color-accent);
  background: rgb(59 130 246 / 10%);
  box-shadow: 0 0 10px rgb(59 130 246 / 14%);
}

.device-icon {
  display: grid;
  place-items: center;
  width: 30px;
  height: 30px;
  color: var(--color-accent);
  border-radius: 5px;
  background: rgb(59 130 246 / 10%);
}

.device-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
}

.device-copy b,
.device-copy small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.device-copy small {
  margin-top: 2px;
  color: var(--text-3);
  font-size: 9.5px;
}

.master-footer {
  display: flex;
  gap: 8px;
  padding: 9px 10px;
  border-top: 1px solid var(--border);
}

.detail-panel {
  display: flex;
  flex-direction: column;
}

.detail-header {
  flex: 0 0 62px;
  min-height: 62px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}

.heading-line {
  display: flex;
  align-items: center;
  gap: 12px;
}

.heading-line h2 {
  font-size: 17px;
}

.detail-header p {
  margin-top: 3px;
  color: var(--text-3);
  font-size: 10px;
}

.detail-tabs {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-height: 0;
}

.detail-tabs :deep(.el-tabs__header) {
  flex: 0 0 auto;
  margin: 0;
  padding: 0 14px;
}

.detail-tabs :deep(.el-tabs__content),
.detail-tabs :deep(.el-tab-pane) {
  height: 100%;
  min-height: 0;
}

.detail-tabs :deep(.el-tabs__content) {
  flex: 1;
  overflow: hidden;
}

.profile-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  height: 100%;
  padding: 12px;
  overflow: auto;
}

.info-card,
.editor-section {
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--bg-panel-2);
}

.info-card h3,
.editor-title b {
  margin-bottom: 10px;
  color: var(--text-2);
  font-size: 12px;
  letter-spacing: 0.04em;
}

dl {
  margin: 0;
}

dl div {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr);
  gap: 12px;
  padding: 8px 0;
  border-bottom: 1px dashed var(--border);
}

dt {
  color: var(--text-3);
}

dd {
  min-width: 0;
  margin: 0;
  overflow-wrap: anywhere;
}

.link-host {
  height: 100%;
}

.template-toolbar {
  padding: 12px 14px;
  border-bottom: 1px solid var(--border);
}

.template-toolbar div {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.template-toolbar span {
  color: var(--text-3);
  font-size: 10.5px;
}

.capability-summary {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 12px;
  height: calc(100% - 59px);
  padding: 12px;
  overflow: auto;
}

.parameter-card {
  grid-column: 1 / -1;
}

.capability-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.page-empty,
.empty-list {
  display: grid;
  height: 100%;
  place-items: center;
  color: var(--text-muted);
}

.template-list-toolbar {
  margin-bottom: 12px;
}

.template-form-scroll {
  max-height: 68vh;
  padding-right: 4px;
  overflow-y: auto;
}

.form-grid.three {
  display: grid;
  grid-template-columns: 1.35fr 1fr 160px;
  gap: 12px;
}

.editor-section + .editor-section {
  margin-top: 12px;
}

.editor-title {
  margin-bottom: 10px;
}

.editor-title b {
  margin: 0;
}

.capability-groups {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.capability-group {
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg-panel);
}

.capability-group strong {
  display: block;
  margin-bottom: 7px;
  color: var(--text-2);
  font-size: 11px;
}

.capability-group :deep(.el-checkbox-group) {
  display: flex;
  flex-direction: column;
}

.capability-group :deep(.el-checkbox) {
  height: auto;
  margin: 3px 0;
}

.capability-group small {
  display: block;
  color: var(--text-muted);
  font-size: 8px;
}

.extension-capabilities {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 7px;
  margin-top: 10px;
  color: var(--text-3);
  font-size: 11px;
}

.extension-capabilities .el-input {
  width: 310px;
}

.advanced-json {
  margin-top: 12px;
}

:deep(.el-select) {
  width: 100%;
}

@media (width <= 1450px) {
  .devices-page {
    grid-template-columns: 260px minmax(590px, 1fr);
  }

  .capability-groups {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
