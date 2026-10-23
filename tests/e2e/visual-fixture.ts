import type { Page, Route } from '@playwright/test'

const fixedNow = '2026-07-24T01:00:00.000Z'
const serverInstanceId = 'visual-server'
const activeDeviceId = 'uav-01'
const activeLinkId = 'link-uav-ros2'

const parameterDefinitions = [
  {
    key: 'navigation.max_speed',
    displayName: '最大航速',
    valueType: 'number',
    defaultValue: 1,
    unit: 'm/s',
    minimum: 0.1,
    maximum: 3,
    step: 0.1,
    description: '自动任务允许的最大航速',
    enumValues: [],
    readOnly: false
  },
  {
    key: 'navigation.return_altitude',
    displayName: '返航高度',
    valueType: 'number',
    defaultValue: 20,
    unit: 'm',
    minimum: 5,
    maximum: 100,
    step: 1,
    description: '执行返航命令时采用的安全高度',
    enumValues: [],
    readOnly: false
  },
  {
    key: 'safety.low_battery',
    displayName: '低电量阈值',
    valueType: 'integer',
    defaultValue: 20,
    unit: '%',
    minimum: 10,
    maximum: 50,
    step: 1,
    description: '触发低电量告警的阈值',
    enumValues: [],
    readOnly: false
  },
  {
    key: 'identity.firmware',
    displayName: '固件版本',
    valueType: 'string',
    defaultValue: 'PM-2.4.1',
    unit: null,
    minimum: null,
    maximum: null,
    step: null,
    description: '设备端上报的固件版本',
    enumValues: [],
    readOnly: true
  }
]

const templates = [
  {
    id: 'template-uav',
    displayName: 'PolarMarine 六旋翼无人机',
    category: 'aerial',
    description: '海洋巡检、取样与目标点飞行平台',
    capabilities: [
      'command.manual_control',
      'command.mode_control',
      'command.arm',
      'command.emergency_stop',
      'mission.waypoint',
      'mission.route',
      'mission.return_home',
      'parameters.read',
      'parameters.write',
      'parameters.persist'
    ],
    parameters: parameterDefinitions,
    mediaChannels: [
      { id: 'front', displayName: '前视相机', role: 'video', required: true },
      { id: 'down', displayName: '下视相机', role: 'video', required: false },
      { id: 'payload', displayName: '载荷相机', role: 'video', required: false },
      { id: 'thermal', displayName: '热成像', role: 'thermal', required: false }
    ],
    revision: 3,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'template-usv',
    displayName: 'PolarMarine 无人船',
    category: 'surface',
    description: '水面巡航、垃圾收集与电磁定位',
    capabilities: [
      'command.manual_control',
      'command.mode_control',
      'command.arm',
      'command.emergency_stop',
      'mission.waypoint',
      'mission.route',
      'mission.return_home',
      'payload.waste_collection',
      'payload.electromagnetic_fix',
      'parameters.read',
      'parameters.write'
    ],
    parameters: parameterDefinitions.slice(0, 3),
    mediaChannels: [
      { id: 'bow', displayName: '船艏相机', role: 'video', required: true },
      { id: 'collector', displayName: '收集机构', role: 'video', required: false }
    ],
    revision: 2,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'template-dock',
    displayName: 'PolarMarine 智能坞站',
    category: 'station',
    description: '返航接驳与无线充电站',
    capabilities: ['command.emergency_stop', 'dock.charge', 'parameters.read', 'parameters.write'],
    parameters: parameterDefinitions.slice(2),
    mediaChannels: [{ id: 'dock', displayName: '坞站监控', role: 'video', required: false }],
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  }
]

const devices = [
  {
    id: activeDeviceId,
    templateId: 'template-uav',
    displayName: '六旋翼无人机 01',
    enabled: true,
    description: '近岸巡检主机',
    tags: ['UAV', '巡检'],
    revision: 2,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'usv-01',
    templateId: 'template-usv',
    displayName: '智能无人船 01',
    enabled: true,
    description: '水面巡检与收集平台',
    tags: ['USV', '收集'],
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'usv-02',
    templateId: 'template-usv',
    displayName: '智能无人船 02',
    enabled: true,
    description: '电磁定位辅助船',
    tags: ['USV', '定位'],
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'dock-01',
    templateId: 'template-dock',
    displayName: '无线充电坞站',
    enabled: true,
    description: '东侧固定坞站',
    tags: ['Dock'],
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'dock-02',
    templateId: 'template-dock',
    displayName: '备用坞站',
    enabled: true,
    description: '离线维护中',
    tags: ['Dock', '备用'],
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  }
]

const links = [
  {
    id: activeLinkId,
    deviceId: activeDeviceId,
    displayName: '局域网 ROS2 主链路',
    driver: 'ros2',
    role: 'primary',
    priority: 10,
    config: { url: 'ws://192.168.8.21:9090' },
    enabled: true,
    revision: 3,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'link-uav-serial',
    deviceId: activeDeviceId,
    displayName: '数传串口辅助链路',
    driver: 'serial_json',
    role: 'auxiliary',
    priority: 20,
    config: { port: 'COM7', baudRate: 115200 },
    enabled: true,
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'link-usv-ros1',
    deviceId: 'usv-01',
    displayName: '局域网 ROS1 主链路',
    driver: 'ros1',
    role: 'primary',
    priority: 10,
    config: { url: 'ws://192.168.8.31:9090' },
    enabled: true,
    revision: 2,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'link-usv-serial',
    deviceId: 'usv-01',
    displayName: '串口热备',
    driver: 'serial_json',
    role: 'auxiliary',
    priority: 20,
    config: { port: 'COM8', baudRate: 115200 },
    enabled: true,
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  },
  {
    id: 'link-dock-ros2',
    deviceId: 'dock-01',
    displayName: '坞站 ROS2',
    driver: 'ros2',
    role: 'primary',
    priority: 10,
    config: { url: 'ws://192.168.8.41:9090' },
    enabled: true,
    revision: 1,
    createdAt: '2026-07-20T01:00:00.000Z',
    updatedAt: fixedNow
  }
]

const linkSessions = [
  {
    linkId: activeLinkId,
    deviceId: activeDeviceId,
    driver: 'ros2',
    state: 'healthy',
    capabilities: templates[0].capabilities,
    startedAt: '2026-07-24T00:30:00.000Z',
    healthySince: '2026-07-24T00:30:05.000Z',
    lastHeartbeatAt: '2026-07-24T00:59:59.600Z',
    latencyMs: 28,
    packetLossPercent: 0.2,
    debugAvailable: true,
    errorCode: null,
    errorMessage: null,
    revision: 12
  },
  {
    linkId: 'link-uav-serial',
    deviceId: activeDeviceId,
    driver: 'serial_json',
    state: 'healthy',
    capabilities: templates[0].capabilities,
    startedAt: '2026-07-24T00:31:00.000Z',
    healthySince: '2026-07-24T00:31:04.000Z',
    lastHeartbeatAt: '2026-07-24T00:59:59.400Z',
    latencyMs: 64,
    packetLossPercent: 0.8,
    debugAvailable: false,
    errorCode: null,
    errorMessage: null,
    revision: 8
  },
  {
    linkId: 'link-usv-ros1',
    deviceId: 'usv-01',
    driver: 'ros1',
    state: 'degraded',
    capabilities: templates[1].capabilities,
    startedAt: '2026-07-24T00:20:00.000Z',
    healthySince: null,
    lastHeartbeatAt: '2026-07-24T00:59:58.000Z',
    latencyMs: 96,
    packetLossPercent: 4.8,
    debugAvailable: true,
    errorCode: 'HIGH_PACKET_LOSS',
    errorMessage: '丢包率升高',
    revision: 14
  },
  {
    linkId: 'link-usv-serial',
    deviceId: 'usv-01',
    driver: 'serial_json',
    state: 'recovering',
    capabilities: templates[1].capabilities,
    startedAt: '2026-07-24T00:45:00.000Z',
    healthySince: null,
    lastHeartbeatAt: '2026-07-24T00:59:55.000Z',
    latencyMs: null,
    packetLossPercent: null,
    debugAvailable: false,
    errorCode: null,
    errorMessage: null,
    revision: 5
  },
  {
    linkId: 'link-dock-ros2',
    deviceId: 'dock-01',
    driver: 'ros2',
    state: 'healthy',
    capabilities: templates[2].capabilities,
    startedAt: '2026-07-24T00:25:00.000Z',
    healthySince: '2026-07-24T00:25:03.000Z',
    lastHeartbeatAt: '2026-07-24T00:59:59.500Z',
    latencyMs: 35,
    packetLossPercent: 0,
    debugAvailable: true,
    errorCode: null,
    errorMessage: null,
    revision: 7
  }
]

const operationalStates = [
  {
    deviceId: activeDeviceId,
    status: 'online',
    activeLinkId,
    healthyLinkIds: [activeLinkId, 'link-uav-serial'],
    lastFailoverAt: null,
    revision: 12
  },
  {
    deviceId: 'usv-01',
    status: 'degraded',
    activeLinkId: 'link-usv-ros1',
    healthyLinkIds: ['link-usv-ros1'],
    lastFailoverAt: '2026-07-24T00:55:00.000Z',
    revision: 14
  },
  {
    deviceId: 'usv-02',
    status: 'offline',
    activeLinkId: null,
    healthyLinkIds: [],
    lastFailoverAt: null,
    revision: 0
  },
  {
    deviceId: 'dock-01',
    status: 'online',
    activeLinkId: 'link-dock-ros2',
    healthyLinkIds: ['link-dock-ros2'],
    lastFailoverAt: null,
    revision: 7
  },
  {
    deviceId: 'dock-02',
    status: 'offline',
    activeLinkId: null,
    healthyLinkIds: [],
    lastFailoverAt: null,
    revision: 0
  }
]

function telemetryValue(value: unknown, unit: string | null, sourceLinkId = activeLinkId) {
  return {
    value,
    sourceLinkId,
    collectedAt: '2026-07-24T00:59:58.900Z',
    receivedAt: '2026-07-24T00:59:59.000Z',
    quality: 'valid',
    unit
  }
}

const telemetrySnapshots = [
  {
    deviceId: activeDeviceId,
    fields: {
      'battery.percent': telemetryValue(82, '%'),
      speed: telemetryValue(0.6, 'm/s'),
      heading: telemetryValue(136, '°'),
      'position.latitude': telemetryValue(38.9242, '°'),
      'position.longitude': telemetryValue(121.6413, '°'),
      'position.altitude': telemetryValue(18.4, 'm'),
      'home.latitude': telemetryValue(38.9237, '°'),
      'home.longitude': telemetryValue(121.6408, '°'),
      'control.mode': telemetryValue('自动巡航', null),
      'control.armed': telemetryValue(true, null),
      'mission.status': telemetryValue('航线巡检中', null)
    },
    revision: 18,
    updatedAt: '2026-07-24T00:59:59.000Z'
  },
  {
    deviceId: 'usv-01',
    fields: {
      'battery.percent': telemetryValue(46, '%', 'link-usv-ros1'),
      speed: telemetryValue(0.9, 'm/s', 'link-usv-ros1'),
      heading: telemetryValue(82, '°', 'link-usv-ros1'),
      'position.latitude': telemetryValue(38.9229, '°', 'link-usv-ros1'),
      'position.longitude': telemetryValue(121.6387, '°', 'link-usv-ros1'),
      'control.mode': telemetryValue('手动', null, 'link-usv-ros1'),
      'mission.status': telemetryValue('待命', null, 'link-usv-ros1')
    },
    revision: 11,
    updatedAt: '2026-07-24T00:59:58.000Z'
  },
  {
    deviceId: 'dock-01',
    fields: {
      'battery.percent': telemetryValue(100, '%', 'link-dock-ros2'),
      'control.mode': telemetryValue('自动', null, 'link-dock-ros2'),
      'mission.status': telemetryValue('坞站可用', null, 'link-dock-ros2')
    },
    revision: 6,
    updatedAt: '2026-07-24T00:59:59.000Z'
  }
]

const alarms = [
  {
    id: 'alarm-link-loss',
    code: 'LINK_PACKET_LOSS',
    severity: 'warning',
    message: '智能无人船 01 主链路丢包率升高',
    deviceId: 'usv-01',
    acknowledged: false,
    createdAt: '2026-07-24T00:57:20.000Z',
    acknowledgedAt: null,
    revision: 1
  },
  {
    id: 'alarm-battery',
    code: 'BATTERY_LOW',
    severity: 'critical',
    message: '备用坞站后备电源低于安全阈值',
    deviceId: 'dock-02',
    acknowledged: false,
    createdAt: '2026-07-24T00:52:10.000Z',
    acknowledgedAt: null,
    revision: 1
  },
  {
    id: 'alarm-history',
    code: 'LINK_RECOVERED',
    severity: 'info',
    message: '六旋翼无人机 01 数传辅助链路已恢复',
    deviceId: activeDeviceId,
    acknowledged: true,
    createdAt: '2026-07-24T00:42:00.000Z',
    acknowledgedAt: '2026-07-24T00:43:00.000Z',
    revision: 2
  }
]

const events = [
  {
    eventId: 'evt-25',
    eventCursor: 25,
    aggregateType: 'mission_run',
    aggregateId: 'run-patrol',
    aggregateRevision: 4,
    occurredAt: '2026-07-24T00:59:12.000Z',
    type: 'mission_run.changed',
    payload: { status: 'running', stepStates: { 'route-1': 'running' } }
  },
  {
    eventId: 'evt-24',
    eventCursor: 24,
    aggregateType: 'command',
    aggregateId: 'command-route',
    aggregateRevision: 3,
    occurredAt: '2026-07-24T00:58:42.000Z',
    type: 'command.changed',
    payload: { commandType: 'start_mission', status: 'in_progress', deviceId: activeDeviceId }
  },
  {
    eventId: 'evt-23',
    eventCursor: 23,
    aggregateType: 'link_session',
    aggregateId: 'link-usv-ros1',
    aggregateRevision: 14,
    occurredAt: '2026-07-24T00:57:20.000Z',
    type: 'link_session.changed',
    payload: { state: 'degraded', latencyMs: 96, packetLossPercent: 4.8 }
  },
  {
    eventId: 'evt-22',
    eventCursor: 22,
    aggregateType: 'device',
    aggregateId: 'dock-01',
    aggregateRevision: 7,
    occurredAt: '2026-07-24T00:55:04.000Z',
    type: 'device.route_changed',
    payload: { activeLinkId: 'link-dock-ros2' }
  },
  {
    eventId: 'evt-21',
    eventCursor: 21,
    aggregateType: 'system',
    aggregateId: 'driver-supervisor',
    aggregateRevision: 5,
    occurredAt: '2026-07-24T00:51:09.000Z',
    type: 'driver.heartbeat',
    payload: { driver: 'ros2', status: 'healthy' }
  }
]

const recentCommands = [
  {
    id: 'command-route',
    deviceId: activeDeviceId,
    commandType: 'start_mission',
    payload: { missionRunId: 'run-patrol' },
    status: 'in_progress',
    progress: 42,
    result: {},
    routedLinkIds: [activeLinkId],
    linkAcknowledgements: { [activeLinkId]: 'accepted' },
    idempotencyKey: 'visual-route',
    reasonCode: null,
    reasonMessage: null,
    requiresStateConfirmation: true,
    createdAt: '2026-07-24T00:58:40.000Z',
    updatedAt: '2026-07-24T00:59:12.000Z',
    expiresAt: null,
    revision: 4
  },
  {
    id: 'command-mode',
    deviceId: activeDeviceId,
    commandType: 'set_mode',
    payload: { mode: 'auto' },
    status: 'completed',
    progress: 100,
    result: { confirmedMode: 'auto' },
    routedLinkIds: [activeLinkId],
    linkAcknowledgements: { [activeLinkId]: 'completed' },
    idempotencyKey: null,
    reasonCode: null,
    reasonMessage: null,
    requiresStateConfirmation: true,
    createdAt: '2026-07-24T00:56:12.000Z',
    updatedAt: '2026-07-24T00:56:13.000Z',
    expiresAt: null,
    revision: 3
  }
]

const missionPlan = {
  id: 'plan-patrol',
  name: '近岸航线巡检',
  description: '[map-quick:v1:uav-01] 由地图页维护的快捷任务，可在任务页继续编辑和执行。',
  steps: [
    {
      id: 'route-1',
      stepType: 'route',
      deviceId: activeDeviceId,
      dependsOn: [],
      timeoutSeconds: 900,
      payload: {
        points: [
          { latitude: 38.9242, longitude: 121.6413, speed: 0.6 },
          { latitude: 38.9261, longitude: 121.6441, speed: 0.6 },
          { latitude: 38.9238, longitude: 121.6472, speed: 0.5 }
        ]
      }
    }
  ],
  version: 3,
  status: 'valid',
  revision: 3,
  createdAt: '2026-07-23T06:20:00.000Z',
  updatedAt: '2026-07-24T00:58:30.000Z'
}

const missionRun = {
  id: 'run-patrol',
  missionPlanId: missionPlan.id,
  missionPlanVersion: missionPlan.version,
  status: 'running',
  stepStates: { 'route-1': 'running' },
  planSteps: missionPlan.steps,
  startedAt: '2026-07-24T00:58:40.000Z',
  endedAt: null,
  revision: 4,
  createdAt: '2026-07-24T00:58:40.000Z'
}

const recordings = [
  {
    id: 'recording-patrol',
    missionRunId: missionRun.id,
    fileName: 'run-patrol.mcap',
    status: 'active',
    sizeBytes: 1_638_400,
    startedAt: '2026-07-24T00:58:40.000Z',
    endedAt: null
  }
]

const parameters = parameterDefinitions.map((definition, index) => ({
  definition,
  value: index === 0 ? 1.2 : index === 1 ? 25 : index === 2 ? 22 : definition.defaultValue,
  source: index === 3 ? 'device' : 'confirmed'
}))

const bootstrap = {
  serverInstanceId,
  eventCursor: 25,
  templates,
  devices,
  links,
  linkSessions,
  operationalStates,
  telemetrySnapshots,
  activeAlarms: alarms.filter((alarm) => !alarm.acknowledged),
  recentCommands,
  activeMissionRuns: [missionRun],
  settings: {
    baiduMapAk: null,
    offlineMapStyleUrl: 'http://127.0.0.1:5173/visual-map-style.json',
    simulatorLabel: '仿真数据',
    maxConfiguredDevices: 50,
    maxOnlineDevices: 20
  }
}

const rosResponses = [
  ['/rosapi/nodes', { nodes: ['/polarmarine/uav_adapter', '/rosbridge_websocket'] }],
  [
    '/rosapi/topics',
    {
      topics: [
        '/polarmarine/v1/state',
        '/polarmarine/v1/command/request',
        '/survey/goal',
        '/survey/cancel',
        '/survey/status'
      ]
    }
  ],
  ['/rosapi/services', { services: ['/rosapi/topics', '/polarmarine/reset_home'] }],
  ['/rosapi/params', { params: ['/polarmarine/device_id', '/polarmarine/max_speed'] }]
] as const

function streamEvents() {
  const ready = {
    schemaVersion: '1.0',
    eventId: 'stream-ready',
    serverInstanceId,
    connectionSequence: 1,
    eventCursor: null,
    aggregateType: 'stream',
    aggregateId: 'connection',
    aggregateRevision: 0,
    occurredAt: fixedNow,
    type: 'stream.ready',
    payload: { resyncRequired: false }
  }
  const debug = rosResponses.map(([service, values], index) => ({
    schemaVersion: '1.0',
    eventId: `debug-response-${index + 1}`,
    serverInstanceId,
    connectionSequence: index + 2,
    eventCursor: null,
    aggregateType: 'debug',
    aggregateId: activeLinkId,
    aggregateRevision: index + 1,
    occurredAt: fixedNow,
    type: 'debug.ros_response',
    payload: {
      linkId: activeLinkId,
      response: { op: 'service_response', service, values }
    }
  }))
  return [ready, ...debug]
}

async function fulfillJson(route: Route, body: unknown, status = 200): Promise<void> {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body)
  })
}

async function handleApi(route: Route): Promise<void> {
  const request = route.request()
  const url = new URL(request.url())
  const path = url.pathname.replace(/^\/api\/v1/, '')
  const method = request.method()

  if (method === 'GET' && path === '/bootstrap') return fulfillJson(route, bootstrap)
  if (method === 'GET' && path === '/events') return fulfillJson(route, events)
  if (method === 'GET' && path === '/alarms') return fulfillJson(route, alarms)
  if (method === 'GET' && path === '/missions') return fulfillJson(route, [missionPlan])
  if (method === 'GET' && path === '/mission-runs') return fulfillJson(route, [missionRun])
  if (method === 'GET' && path === '/recordings') return fulfillJson(route, recordings)
  if (method === 'GET' && path.endsWith('/versions')) return fulfillJson(route, [missionPlan])
  if (method === 'GET' && path.endsWith('/parameters')) return fulfillJson(route, parameters)
  if (method === 'GET' && path.startsWith('/devices/') && path.endsWith('/links')) {
    const deviceId = decodeURIComponent(path.split('/')[2] ?? '')
    return fulfillJson(
      route,
      links.filter((link) => link.deviceId === deviceId)
    )
  }
  if (method === 'GET' && path === '/device-templates') return fulfillJson(route, templates)
  if (method === 'GET' && path === '/devices') return fulfillJson(route, devices)
  if (method === 'POST' && path === '/debug/ros') {
    return fulfillJson(route, { accepted: true, isolated: true })
  }
  if (method === 'GET' && path === '/debug/serial/ports') {
    return fulfillJson(route, { ok: true, ports: [{ device: 'COM7' }, { device: 'COM8' }] })
  }
  if (method === 'GET' && path === '/discovery/network') {
    return fulfillJson(route, { ok: true, driver: 'ros2', candidates: [] })
  }
  if (method === 'GET' && path.includes('/recordings/')) return fulfillJson(route, [])

  return fulfillJson(
    route,
    {
      error: {
        code: 'VISUAL_FIXTURE_UNHANDLED',
        message: `${method} ${path} is not part of the read-only visual fixture`,
        details: {}
      }
    },
    501
  )
}

export async function installVisualFixture(page: Page, theme: 'dark' | 'light' = 'dark') {
  await page.clock.setFixedTime(new Date(fixedNow))
  await page.addInitScript(
    ({ selectedTheme, eventsForStream }) => {
      window.localStorage.setItem('polarmarine-gcs-theme', selectedTheme)
      class VisualWebSocket {
        static readonly CONNECTING = 0
        static readonly OPEN = 1
        static readonly CLOSING = 2
        static readonly CLOSED = 3

        readonly url: string
        readyState = VisualWebSocket.CONNECTING
        onmessage: ((event: MessageEvent<string>) => void) | null = null
        onerror: ((event: Event) => void) | null = null
        onclose: ((event: CloseEvent) => void) | null = null

        constructor(url: string | URL) {
          this.url = String(url)
          window.setTimeout(() => {
            this.readyState = VisualWebSocket.OPEN
            eventsForStream.forEach((event, index) => {
              window.setTimeout(() => {
                this.onmessage?.(
                  new MessageEvent('message', {
                    data: JSON.stringify(event)
                  })
                )
              }, index * 5)
            })
          }, 0)
        }

        close(): void {
          this.readyState = VisualWebSocket.CLOSED
        }

        send(): void {
          // The production event stream is receive-only.
        }
      }

      Object.defineProperty(window, 'WebSocket', {
        configurable: true,
        value: VisualWebSocket
      })
    },
    { selectedTheme: theme, eventsForStream: streamEvents() }
  )
  await page.route('**/visual-map-style.json', (route) =>
    fulfillJson(route, {
      version: 8,
      sources: {},
      layers: [
        {
          id: 'background',
          type: 'background',
          paint: { 'background-color': theme === 'dark' ? '#071426' : '#dce7f5' }
        }
      ]
    })
  )
  await page.route('**/api/v1/**', handleApi)
}
