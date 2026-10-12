export const AGV_STATUS = {
  IDLE: 'IDLE',
  MOVE_TO_PICKUP: 'MOVE_TO_PICKUP',
  WAIT_FOR_PICKUP: 'WAIT_FOR_PICKUP',
  HANDOVER_PICKUP: 'HANDOVER_PICKUP',
  MOVE_TO_DROPOFF: 'MOVE_TO_DROPOFF',
  WAIT_FOR_DROPOFF: 'WAIT_FOR_DROPOFF',
  HANDOVER_DROPOFF: 'HANDOVER_DROPOFF',
  RETURNING: 'RETURNING',
  BROKEN_DOWN: 'BROKEN_DOWN',
  BROKEN_RETURNING: 'BROKEN_RETURNING',
  DECOMMISSIONED: 'DECOMMISSIONED',
  BLOCKED_BY_RISK: 'BLOCKED_BY_RISK',
  PAUSED_BY_RISK: 'PAUSED_BY_RISK',
} as const

export const STATUS_COLORS: Record<string, string> = {
  IDLE: '#38a169',
  MOVE_TO_PICKUP: '#3182ce',
  WAIT_FOR_PICKUP: '#805ad5',
  HANDOVER_PICKUP: '#d69e2e',
  MOVE_TO_DROPOFF: '#dd6b20',
  WAIT_FOR_DROPOFF: '#805ad5',
  HANDOVER_DROPOFF: '#d69e2e',
  RETURNING: '#319795',
  BROKEN_DOWN: '#e53e3e',
  BROKEN_RETURNING: '#c53030',
  DECOMMISSIONED: '#a0aec0',
  BLOCKED_BY_RISK: '#c05621',
  PAUSED_BY_RISK: '#b83280',
}

export const STATUS_LABELS: Record<string, string> = {
  IDLE: 'Idle',
  MOVE_TO_PICKUP: 'To Pickup',
  WAIT_FOR_PICKUP: 'Waiting at Pickup',
  HANDOVER_PICKUP: 'Pickup Handover',
  MOVE_TO_DROPOFF: 'Carrying',
  WAIT_FOR_DROPOFF: 'Waiting at Drop-off',
  HANDOVER_DROPOFF: 'Drop-off Handover',
  RETURNING: 'Returning',
  BROKEN_DOWN: 'Breakdown',
  BROKEN_RETURNING: 'Breakdown, Returning',
  DECOMMISSIONED: 'Decommissioned',
  BLOCKED_BY_RISK: 'Blocked by Risk',
  PAUSED_BY_RISK: 'Paused by Risk',
}

export const statusColor = (status: string): string =>
  STATUS_COLORS[status] || '#718096'

export const statusLabel = (status: string): string =>
  STATUS_LABELS[status] || status

export const RISK_TYPE = {
  FIRE: 'FIRE',
  PERSONNEL_INTRUSION: 'PERSONNEL_INTRUSION',
  TRAFFIC_CONGESTION: 'TRAFFIC_CONGESTION',
  AGV_FAILURE: 'AGV_FAILURE',
  NO_HELMET: 'NO_HELMET',
  SMOKING: 'SMOKING',
} as const

export type RiskTypeValue = (typeof RISK_TYPE)[keyof typeof RISK_TYPE]

export const RISK_COLORS: Record<string, string> = {
  FIRE: '#e53e3e',
  PERSONNEL_INTRUSION: '#dd6b20',
  TRAFFIC_CONGESTION: '#805ad5',
  AGV_FAILURE: '#1a202c',
  NO_HELMET: '#d69e2e',
  SMOKING: '#718096',
}

export const RISK_LABELS: Record<string, string> = {
  FIRE: 'Fire',
  PERSONNEL_INTRUSION: 'Personnel Intrusion',
  TRAFFIC_CONGESTION: 'Traffic Congestion',
  AGV_FAILURE: 'AGV Failure',
  NO_HELMET: 'No Helmet',
  SMOKING: 'Smoking',
}

export const riskColor = (type: string): string =>
  RISK_COLORS[type] || '#e53e3e'

export const riskLabel = (type: string): string =>
  RISK_LABELS[type] || type

export const RISK_BUTTONS: {
  type: RiskTypeValue
  label: string
  hint: string
}[] = [
  { type: 'FIRE', label: 'Inject Fire', hint: 'Locks down the job point; its task returns to the queue' },
  { type: 'SMOKING', label: 'Detect Smoking', hint: 'Alert only; scheduling is unchanged' },
  { type: 'NO_HELMET', label: 'No Helmet', hint: 'Locks down the job point; its task returns to the queue' },
  { type: 'PERSONNEL_INTRUSION', label: 'Personnel Intrusion', hint: 'Pauses every AGV inside the highway area' },
  { type: 'TRAFFIC_CONGESTION', label: 'Inject Congestion', hint: 'Blocks waypoints in radius; A* reroutes' },
  { type: 'AGV_FAILURE', label: 'AGV Failure', hint: 'AGV releases its task and returns to the depot' },
]
