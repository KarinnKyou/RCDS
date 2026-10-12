import { useSimulationStore } from '../../stores/simulationStore'
import type { AGVState } from '../../stores/simulationStore'
import { statusColor, statusLabel } from '../../theme'
import { StatusDonut } from './StatusDonut'

export function MetricsPanel() {
  const {
    kpis, agvStates, agvEfficiency, statusDistribution,
    selectedAgvId, setSelectedAgv, setShowAgvDetail } = useSimulationStore()

  return (
    <aside className="metrics-panel">
      <div className="panel-header">
        <svg className="panel-header__icon" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2">
          <path d="M3 3v18h18" />
          <path d="M18 17V9" />
          <path d="M13 17V5" />
          <path d="M8 17v-3" />
        </svg>
        <span className="panel-header__title">Performance</span>
      </div>

      <div className="metrics-grid">
        <div className="metric-card">
          <div className="metric-card__header">
            <span className="metric-card__label">Task Completion</span>
            <span className="metric-card__badge">{kpis.completionRate}%</span>
          </div>
          <div className="metric-card__value">
            {kpis.taskCompleted}
            <span style={{ color: 'var(--text-tertiary)', fontSize: '14px' }}>
              {' '}/ {kpis.taskTotal}
            </span>
          </div>
          <div className="metric-progress">
            <div className="metric-progress__bar"
                 style={{ width: `${kpis.completionRate}%` }} />
          </div>
        </div>

        <div className="kpi-row">
          <div className="metric-card metric-card--compact">
            <div className="metric-card__label">Utilization</div>
            <div className="metric-card__value metric-card__value--highlight">
              {kpis.utilizationRate}%
            </div>
          </div>
          <div className="metric-card metric-card--compact">
            <div className="metric-card__label">Blocked Share</div>
            <div className="metric-card__value">{kpis.blockedRate}%</div>
          </div>
        </div>

        <div className="kpi-row">
          <div className="metric-card metric-card--compact">
            <div className="metric-card__label">Avg Task Time</div>
            <div className="metric-card__value">
              {kpis.avgTaskDuration}
              <span className="metric-card__unit">tick</span>
            </div>
          </div>
          <div className="metric-card metric-card--compact">
            <div className="metric-card__label">Total Distance</div>
            <div className="metric-card__value">
              {kpis.totalDistanceKm}
              <span className="metric-card__unit">km</span>
            </div>
          </div>
        </div>

        <div className="kpi-row">
          <div className="metric-card metric-card--compact">
            <div className="metric-card__label">Queued / Running</div>
            <div className="metric-card__value">
              {kpis.taskPending}
              <span className="metric-card__unit">/ {kpis.taskAssigned}</span>
            </div>
          </div>
          <div className="metric-card metric-card--compact">
            <div className="metric-card__label">Avg Battery</div>
            <div className="metric-card__value">{kpis.avgBattery}%</div>
          </div>
        </div>

      </div>

      <div className="panel-section">
        <div className="panel-section__title">Fleet Status</div>
        <StatusDonut data={statusDistribution} total={agvStates.length} />
      </div>

      <div className="panel-section">
        <div className="panel-section__title">Vehicle Efficiency</div>
        <table className="mini-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Dist.</th>
              <th>Loaded</th>
              <th>Empty</th>
              <th>Blocked</th>
            </tr>
          </thead>
          <tbody>
            {agvEfficiency.length === 0 && (
              <tr><td colSpan={5} className="mini-table__empty">Waiting for simulation</td></tr>
            )}
            {agvEfficiency.map((row) => (
              <tr
                key={row.id}
                className={selectedAgvId === row.id ? 'mini-table__row--active' : ''}
                onClick={() => setSelectedAgv(selectedAgvId === row.id ? null : row.id)}
              >
                <td className="mono">{row.id.replace('AGV-', 'A')}</td>
                <td className="mono">{(row.distanceM / 1000).toFixed(1)}k</td>
                <td className="mono">{row.loadedPct}%</td>
                <td className="mono">{row.idlePct}%</td>
                <td className="mono">{row.blockedPct}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="agv-status-section">
        <div className="agv-status-header">Vehicle Status</div>
        <div className="agv-status-grid">
          {agvStates.length === 0 && (
            <div className="agv-status-empty">Disconnected · waiting for backend</div>
          )}
          {agvStates.map((agv: AGVState) => (
            <div
              key={agv.id}
              className={`agv-status-item ${selectedAgvId === agv.id ? 'agv-status-item--selected' : ''}`}
              onClick={() => {
                setSelectedAgv(selectedAgvId === agv.id ? null : agv.id)
                setShowAgvDetail(true)
              }}
            >
              <div
                className="agv-status-item__indicator"
                style={{ background: statusColor(agv.status) }}
              />
              <span className="agv-status-item__id">{agv.id}</span>
              <span className="agv-status-item__state">
                {agv.statusLabel || statusLabel(agv.status)}
              </span>
              <span className="agv-status-item__battery">
                {agv.battery.toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}
