import { z } from 'zod'

const timestamp = z.string().datetime({ offset: true })
const nullableTimestamp = timestamp.nullable()
const linkState = z.enum([
  'stopped',
  'starting',
  'handshaking',
  'healthy',
  'degraded',
  'recovering',
  'failed'
])

export const linkSessionPayloadSchema = z.object({
  linkId: z.string().min(1),
  deviceId: z.string().min(1),
  driver: z.enum(['ros1', 'ros2', 'serial_json', 'simulator']),
  state: linkState,
  capabilities: z.array(z.string()),
  startedAt: nullableTimestamp,
  healthySince: nullableTimestamp,
  lastHeartbeatAt: nullableTimestamp,
  latencyMs: z.number().nullable(),
  packetLossPercent: z.number().nullable(),
  debugAvailable: z.boolean(),
  errorCode: z.string().nullable(),
  errorMessage: z.string().nullable(),
  revision: z.number().int().nonnegative()
})

export const routeChangedPayloadSchema = z.object({
  deviceId: z.string().min(1),
  previousLinkId: z.string().nullable(),
  activeLinkId: z.string().nullable(),
  occurredAt: timestamp
})

const telemetryValueSchema = z.object({
  value: z.unknown(),
  sourceLinkId: z.string().min(1),
  collectedAt: timestamp,
  receivedAt: timestamp,
  quality: z.enum(['unknown', 'valid', 'stale', 'invalid', 'simulated']),
  unit: z.string().nullable()
})

export const telemetryPayloadSchema = z.object({
  deviceId: z.string().min(1),
  fields: z.record(z.string(), telemetryValueSchema),
  updatedAt: timestamp
})

export const commandPayloadSchema = z.object({
  id: z.string().min(1),
  deviceId: z.string().min(1),
  commandType: z.enum([
    'manual_control',
    'set_mode',
    'set_armed',
    'emergency_stop',
    'start_mission',
    'pause_mission',
    'resume_mission',
    'cancel_mission',
    'return_home',
    'read_parameters',
    'write_parameters',
    'custom_action'
  ]),
  payload: z.record(z.string(), z.unknown()),
  status: z.enum([
    'queued',
    'dispatched',
    'accepted',
    'in_progress',
    'completed',
    'rejected',
    'timed_out',
    'cancelled',
    'state_unconfirmed'
  ]),
  progress: z.number().nullable(),
  result: z.record(z.string(), z.unknown()),
  routedLinkIds: z.array(z.string()),
  linkAcknowledgements: z.record(z.string(), z.string()),
  idempotencyKey: z.string().nullable(),
  reasonCode: z.string().nullable(),
  reasonMessage: z.string().nullable(),
  requiresStateConfirmation: z.boolean(),
  createdAt: timestamp,
  updatedAt: timestamp,
  expiresAt: nullableTimestamp,
  revision: z.number().int().nonnegative()
})

export const missionRunPayloadSchema = z.object({
  id: z.string().min(1),
  missionPlanId: z.string().min(1),
  status: z.enum(['queued', 'running', 'paused', 'completed', 'failed', 'cancelled']),
  stepStates: z.record(z.string(), z.string()),
  reason: z.string().nullable()
})

const streamReadyPayloadSchema = z
  .object({
    resyncRequired: z.boolean()
  })
  .passthrough()

const knownPayloadSchemas: Record<string, z.ZodType> = {
  'stream.ready': streamReadyPayloadSchema,
  'link_session.changed': linkSessionPayloadSchema,
  'device.route_changed': routeChangedPayloadSchema,
  'telemetry.updated': telemetryPayloadSchema,
  'telemetry.quality_changed': telemetryPayloadSchema,
  'command.changed': commandPayloadSchema,
  'mission_run.changed': missionRunPayloadSchema
}

export const streamEventSchema = z
  .object({
    schemaVersion: z.literal('1.0'),
    eventId: z.string().min(1),
    serverInstanceId: z.string().min(1),
    connectionSequence: z.number().int().nonnegative(),
    eventCursor: z.number().int().nonnegative().nullable(),
    aggregateType: z.string(),
    aggregateId: z.string(),
    aggregateRevision: z.number().int().nonnegative(),
    occurredAt: timestamp,
    type: z.string().min(1),
    payload: z.record(z.string(), z.unknown())
  })
  .superRefine((event, context) => {
    const payloadSchema = knownPayloadSchemas[event.type]
    if (!payloadSchema) return
    const result = payloadSchema.safeParse(event.payload)
    if (result.success) return
    for (const issue of result.error.issues) {
      context.addIssue({
        code: 'custom',
        path: ['payload', ...issue.path],
        message: issue.message
      })
    }
  })

export type StreamEvent = z.infer<typeof streamEventSchema>
