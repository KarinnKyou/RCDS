import { PortScene } from './components/Scene3D/PortScene'
import { Map2D } from './components/View2D/Map2D'
import { ControlPanel } from './components/UI/ControlPanel'
import { StatusBar } from './components/UI/StatusBar'
import { MetricsPanel } from './components/UI/MetricsPanel'
import { RiskPanel } from './components/UI/RiskPanel'
import { RescheduleLog } from './components/UI/RescheduleLog'
import { TaskTable } from './components/UI/TaskTable'
import { AgvDetailModal } from './components/UI/AgvDetailModal'
import { useSimulationStore } from './stores/simulationStore'
import { useSimulationWebSocket } from './hooks/useWebSocket'
import './App.css'

function App() {
  const {
    isConnected, isRunning, time, risks, rescheduleLog, apiStatus,
    stats, viewMode, setViewMode,
  } = useSimulationStore()

  const {
    start, pause, step, reset, setSpeed,
    addRisk, clearRisks, setApiSimulation, triggerRiskSequence,
  } = useSimulationWebSocket()

  return (
    <div className="app">
      <StatusBar isConnected={isConnected} isRunning={isRunning} time={time} />

      <div className="main-content">
        <MetricsPanel />

        <div className="viewport">
          {viewMode === '3d' ? <PortScene /> : <Map2D />}

          <div className="viewport-switch" role="group" aria-label="Viewport mode">
            <button
              className={`viewport-switch__btn ${viewMode === '3d' ? 'viewport-switch__btn--active' : ''}`}
              onClick={() => setViewMode('3d')}
              title="3D scene: road network / cranes / fleet / risk markers"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 2L2 7l10 5 10-5-10-5z" />
                <path d="M2 17l10 5 10-5" />
                <path d="M2 12l10 5 10-5" />
              </svg>
              3D
            </button>
            <button
              className={`viewport-switch__btn ${viewMode === '2d' ? 'viewport-switch__btn--active' : ''}`}
              onClick={() => setViewMode('2d')}
              title="2D top-down map: quay crane area / yard blocks / vessels / risk zones"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="1" />
                <path d="M3 9h18M3 15h18M9 3v18M15 3v18" />
              </svg>
              2D
            </button>
          </div>

          <div className="viewport-overlay">
            <div className="viewport-label">
              {viewMode === '3d' ? '3D VIEWPORT' : '2D MAP VIEW'}
            </div>
          </div>
        </div>

        <div className="right-rail">
          <ControlPanel
            isRunning={isRunning}
            onStart={start}
            onPause={pause}
            onReset={reset}
            onStep={step}
            onSpeedChange={setSpeed}
          />
          <RiskPanel
            onAddRisk={addRisk}
            onClearRisks={clearRisks}
            onToggleApi={setApiSimulation}
            onTriggerSequence={triggerRiskSequence}
          />
        </div>
      </div>

      <div className="bottom-dock">
        <RescheduleLog />
        <TaskTable />
      </div>

      <div className="info-bar">
        <span className="info-item">RCDS-SIM SHELL</span>
        <span className="info-divider" />
        <span className="info-item">KERNEL: A* REACTIVE RESCHEDULING</span>
        <span className="info-divider" />
        <span className="info-item">
          FLEET: {stats.activeAgvs} ACTIVE / {stats.totalTasks} TASKS
        </span>
        <span className="info-divider" />
        <span className="info-item">
          TASKS DONE: {stats.completedTasks}/{stats.totalTasks}
        </span>
        <span className="info-divider" />
        <span className={`info-item ${risks.length > 0 ? 'info-item--warn' : ''}`}>
          RISKS: {risks.length} ACTIVE
        </span>
        <span className="info-divider" />
        <span className="info-item">
          RESCHEDULE EVENTS: {rescheduleLog.length}
        </span>
        <span className="info-divider" />
        <span className="info-item">
          API: {apiStatus?.enabled ? 'CONNECTED' : 'OFF'}
        </span>
        <span className="info-divider" />
        <span className="info-item">REFRESH: 500ms</span>
      </div>

      <AgvDetailModal />
    </div>
  )
}

export default App
