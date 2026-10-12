import { useSimulationStore } from '../../stores/simulationStore'

interface StatusBarProps {
  isConnected: boolean
  isRunning: boolean
  time: number
}

export function StatusBar({ isConnected, isRunning, time }: StatusBarProps) {
  const { risks, rescheduleLog, apiStatus, kpis, finished } =
    useSimulationStore()

  return (
    <header className="status-bar">
      <div className="status-bar__brand">
        <div className="status-bar__logo">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
        <span className="status-bar__title">RCDS-SIM</span>
        <span className="status-bar__subtitle">Risk-Responsive Coordinated Dispatch</span>
      </div>

      <div className="status-bar__divider" />

      <div className="status-bar__metrics">
        <div className="status-metric">
          <span className="status-metric__label">TICK</span>
          <span className="status-metric__value status-metric__value--mono">
            {time}
          </span>
        </div>
        <div className="status-metric">
          <span className="status-metric__label">Completion</span>
          <span className="status-metric__value status-metric__value--mono">
            {kpis.completionRate}%
          </span>
        </div>
        <div className="status-metric">
          <span className="status-metric__label">Active Risks</span>
          <span
            className={`status-metric__value status-metric__value--mono ${risks.length > 0 ? 'status-metric__value--alert' : ''}`}
          >
            {risks.length}
          </span>
        </div>
        <div className="status-metric">
          <span className="status-metric__label">Reschedules</span>
          <span className="status-metric__value status-metric__value--mono">
            {rescheduleLog.length}
          </span>
        </div>
        <div className="status-metric">
          <span className="status-metric__label">Model Service</span>
          <span className="status-metric__value status-metric__value--mono">
            {apiStatus?.enabled ? 'Connected' : 'Offline'}
          </span>
        </div>
      </div>

      <div className="status-bar__status">
        <div
          className={`status-indicator ${isConnected ? 'status-indicator--online' : ''} ${isRunning ? 'status-indicator--running' : ''}`}
        />
        <span className="status-text">
          {!isConnected
            ? 'DISCONNECTED'
            : finished
              ? 'FINISHED'
              : isRunning
                ? 'RUNNING'
                : 'READY'}
        </span>
      </div>
    </header>
  )
}
