import { useSimulationStore } from '../../stores/simulationStore'
import { RISK_BUTTONS, riskColor } from '../../theme'

interface RiskPanelProps {
  onAddRisk: (riskType: string) => void
  onClearRisks: () => void
  onToggleApi: (enabled: boolean) => void
  onTriggerSequence: () => void
}

export function RiskPanel({
  onAddRisk,
  onClearRisks,
  onToggleApi,
  onTriggerSequence,
}: RiskPanelProps) {
  const { risks, apiStatus, isConnected } = useSimulationStore()
  const apiOn = apiStatus?.enabled ?? false

  return (
    <aside className="risk-panel">
      <div className="panel-header">
        <svg className="panel-header__icon" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2">
          <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
          <path d="M12 8v4" />
          <path d="M12 16h.01" />
        </svg>
        <span className="panel-header__title">Risk Simulation</span>
        {risks.length > 0 && (
          <span className="panel-badge panel-badge--danger">{risks.length}</span>
        )}
      </div>

      <div className="control-section">
        <div className="control-section__title">Inject Hazard</div>
        <div className="risk-grid">
          {RISK_BUTTONS.map((btn) => (
            <button
              key={btn.type}
              className="risk-btn"
              disabled={!isConnected}
              title={btn.hint}
              onClick={() => onAddRisk(btn.type)}
              style={{ ['--risk-color' as string]: riskColor(btn.type) }}
            >
              <span className="risk-btn__dot" />
              <span className="risk-btn__label">{btn.label}</span>
            </button>
          ))}
        </div>
        <button
          className="control-btn control-btn--danger risk-clear"
          onClick={onClearRisks}
          disabled={!isConnected || risks.length === 0}
        >
          Clear All Risks
        </button>
      </div>

      <div className="control-section">
        <div className="control-section__title">Model Service (API)</div>

        <div className="api-row">
          <button
            className={`control-btn ${apiOn ? 'control-btn--active' : 'control-btn--primary'}`}
            style={{ flex: 1 }}
            disabled={!isConnected}
            onClick={() => onToggleApi(!apiOn)}
          >
            {apiOn ? 'Disconnect API' : 'Connect API'}
          </button>
          <button
            className="control-btn"
            style={{ flex: 1 }}
            disabled={!isConnected}
            onClick={onTriggerSequence}
            title="Inject the six risk types in the preset sequence"
          >
            Risk Sequence
          </button>
        </div>

        <div className="api-meta">
          <span className={`api-dot ${apiOn ? 'api-dot--on' : ''}`} />
          {apiOn
            ? `Polling · every ${apiStatus?.pollTicks ?? 15} ticks`
            : 'Offline'}
          <span className="api-meta__src">
            {apiStatus?.realApi ? 'Live HTTP' : 'Mock detector'}
          </span>
        </div>
      </div>

      <div className="control-section control-section--grow">
        <div className="control-section__title">
          Active Alerts
          {risks.length > 0 && <span className="section-count">{risks.length}</span>}
        </div>
        <div className="alert-feed">
          {risks.length === 0 && (
            <div className="alert-empty">No active risks, fleet operating normally</div>
          )}
          {risks.map((risk) => (
            <div key={risk.id} className="alert-item"
                 style={{ ['--risk-color' as string]: riskColor(risk.type) }}>
              <div className="alert-item__head">
                <span className="alert-item__label">{risk.label}</span>
                <span className="alert-item__time">T{risk.createdTime}</span>
              </div>
              <div className="alert-item__msg">{risk.message}</div>
              <div className="alert-item__meta">
                {risk.source === 'api' ? 'model service' : 'manual'}
                {risk.affectedCount > 0 && ` · ${risk.affectedCount} waypoints blocked`}
              </div>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}
