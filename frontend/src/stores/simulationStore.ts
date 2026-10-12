import { create } from 'zustand'

export type AGVState = {
  id: string
  position: { x: number; y: number; z: number }
  rotation: number
  status: string
  statusLabel: string
  battery: number
  taskId: string | null
  currentWp: string
  targetWp: string | null
  pickupLoc: string | null
  dropoffLoc: string | null
  handoverTimer: number
  distanceM: number

  path: string[]

  historyPath: string[]
  log: string[]
  broken: boolean
}

export type TaskInfo = {
  id: string
  type: string
  pickup_loc_id: string
  dropoff_loc_id: string
  status: 'PENDING' | 'ASSIGNED' | 'COMPLETED' | 'FAILED' | string
  assigned_agv_id: string | null
  created_time: number
  assigned_time: number | null
  completed_time: number | null
}

export type RiskInfo = {
  id: string
  seq: number
  type: string
  label: string
  severity: string
  zone: string
  targetId: string
  agvId: string | null
  locationWp: string | null
  position: { x: number; y: number; z: number } | null
  message: string
  source: string
  createdTime: number
  affectedCount: number

  affectedWaypoints?: string[]
}

export type RescheduleEntry = {
  seq: number
  time: number
  agvId: string
  reason: string
  method: string
  result: string
}

export type Kpis = {
  time: number
  taskTotal: number
  taskCompleted: number
  taskPending: number
  taskAssigned: number
  taskFailed: number
  completionRate: number
  utilizationRate: number
  blockedRate: number
  avgTaskDuration: number
  totalDistanceKm: number
  avgBattery: number

}

export type AgvEfficiency = {
  id: string
  status: string
  statusLabel: string
  distanceM: number
  battery: number
  loadedPct: number
  emptyPct: number
  idlePct: number
  blockedPct: number
  taskId: string | null
  totalTime: number
}

export type StatusCount = {
  status: string
  label: string
  count: number
}

export type ApiEndpoint = {
  key: string
  path: string
  label: string
  scope: string[]
  format: string
  riskType: string
  lastWarn: number | null
  lastTime: number | null
  lastDetail: string
}

export type ApiStatus = {
  enabled: boolean
  realApi: boolean
  baseUrl: string
  pollTicks: number
  endpoints: ApiEndpoint[]
  cameras: Record<string, string[]>
}

export type JobLocationState = {
  status: string
  agv_id: string | null
  type: string
}

export type NetworkNode = {
  id: string
  position: { x: number; y: number; z: number }
  type: string
}

export type NetworkEdge = {
  from: string
  to: string
  distance: number
}

export type JobPoint = {
  id: string
  pos: { x: number; y: number; z: number }
  areaNo: string
  bay: string
  width: number
  height: number
}

export type Stats = {
  totalTasks: number
  completedTasks: number
  activeAgvs: number
}

export type SimulationConfig = {
  numAgvs: number
  numTasks: number
}

export type CameraPreset = 'top' | 'front' | 'side' | 'iso' | null

export type ViewMode = '3d' | '2d'

export type CameraPosition = {
  position: [number, number, number]
  target: [number, number, number]
}

export const CAMERA_PRESETS: Record<Exclude<CameraPreset, null>, CameraPosition> = {
  top: {
    position: [600, 1250, -250],
    target: [600, 0, -250],
  },
  front: {
    position: [600, 230, 900],
    target: [600, 0, -230],
  },
  side: {
    position: [1500, 300, -250],
    target: [600, 0, -250],
  },
  iso: {
    position: [1150, 580, 700],
    target: [600, 0, -250],
  },
}

const EMPTY_KPIS: Kpis = {
  time: 0,
  taskTotal: 0,
  taskCompleted: 0,
  taskPending: 0,
  taskAssigned: 0,
  taskFailed: 0,
  completionRate: 0,
  utilizationRate: 0,
  blockedRate: 0,
  avgTaskDuration: 0,
  totalDistanceKm: 0,
  avgBattery: 0,
}

interface SimulationStore {

  isConnected: boolean
  setConnected: (connected: boolean) => void

  isRunning: boolean
  setRunning: (running: boolean) => void
  time: number
  setTime: (time: number) => void
  makespan: number
  setMakespan: (makespan: number) => void
  finished: boolean
  setFinished: (finished: boolean) => void

  agvStates: AGVState[]
  tasks: TaskInfo[]
  risks: RiskInfo[]
  rescheduleLog: RescheduleEntry[]
  setFleet: (payload: {
    agvs: AGVState[]
    tasks: TaskInfo[]
    risks: RiskInfo[]
    rescheduleLog: RescheduleEntry[]
  }) => void

  kpis: Kpis
  agvEfficiency: AgvEfficiency[]
  statusDistribution: StatusCount[]
  setMetrics: (payload: {
    kpis?: Kpis
    agvEfficiency?: AgvEfficiency[]
    statusDistribution?: StatusCount[]
  }) => void

  apiStatus: ApiStatus | null
  setApiStatus: (status: ApiStatus) => void

  jobLocationStates: Record<string, JobLocationState>
  setJobLocationStates: (states: Record<string, JobLocationState>) => void


  networkNodes: NetworkNode[]
  networkEdges: NetworkEdge[]
  jobPoints: Record<string, JobPoint>
  setNetworkData: (nodes: NetworkNode[], edges: NetworkEdge[]) => void
  setJobPoints: (points: Record<string, JobPoint>) => void

  stats: Stats
  setStats: (stats: Stats) => void

  config: SimulationConfig
  setConfig: (config: Partial<SimulationConfig>) => void

  selectedAgvId: string | null
  setSelectedAgv: (id: string | null) => void

  cameraPreset: CameraPreset
  setCameraPreset: (preset: CameraPreset) => void
  cameraUpdateTrigger: number

  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void

  showAgvDetail: boolean
  setShowAgvDetail: (show: boolean) => void
}

export const useSimulationStore = create<SimulationStore>((set) => ({
  isConnected: false,
  setConnected: (connected) => set({ isConnected: connected }),

  isRunning: false,
  setRunning: (running) => set({ isRunning: running }),
  time: 0,
  setTime: (time) => set({ time }),
  makespan: 0,
  setMakespan: (makespan) => set({ makespan }),
  finished: false,
  setFinished: (finished) => set({ finished }),

  agvStates: [],
  tasks: [],
  risks: [],
  rescheduleLog: [],
  setFleet: ({ agvs, tasks, risks, rescheduleLog }) =>
    set({
      agvStates: agvs,
      tasks,
      risks,
      rescheduleLog,
    }),

  kpis: EMPTY_KPIS,
  agvEfficiency: [],
  statusDistribution: [],
  setMetrics: ({ kpis, agvEfficiency, statusDistribution }) =>
    set((state) => ({
      kpis: kpis ?? state.kpis,
      agvEfficiency: agvEfficiency ?? state.agvEfficiency,
      statusDistribution: statusDistribution ?? state.statusDistribution,
    })),

  apiStatus: null,
  setApiStatus: (status) => set({ apiStatus: status }),

  jobLocationStates: {},
  setJobLocationStates: (states) => set({ jobLocationStates: states }),


  networkNodes: [],
  networkEdges: [],
  jobPoints: {},
  setNetworkData: (nodes, edges) =>
    set({ networkNodes: nodes, networkEdges: edges }),
  setJobPoints: (points) => set({ jobPoints: points }),

  stats: { totalTasks: 0, completedTasks: 0, activeAgvs: 0 },
  setStats: (stats) => set({ stats }),

  config: { numAgvs: 5, numTasks: 100 },
  setConfig: (newConfig) =>
    set((state) => ({ config: { ...state.config, ...newConfig } })),

  selectedAgvId: null,
  setSelectedAgv: (id) => set({ selectedAgvId: id }),

  cameraPreset: null,
  setCameraPreset: (preset) =>
    set((state) => ({
      cameraPreset: preset,
      cameraUpdateTrigger: state.cameraUpdateTrigger + 1,
    })),
  cameraUpdateTrigger: 0,

  viewMode: '3d',
  setViewMode: (mode) => set({ viewMode: mode }),

  showAgvDetail: false,
  setShowAgvDetail: (show) => set({ showAgvDetail: show }),
}))
