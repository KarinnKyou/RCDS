import { useSimulationStore } from '../../stores/simulationStore'
import { statusColor } from '../../theme'

export function AgvDetailModal() {
  const {
    agvStates, selectedAgvId, showAgvDetail, setShowAgvDetail,
    setSelectedAgv, tasks,
  } = useSimulationStore()

  const agv = agvStates.find((a) => a.id === selectedAgvId) || null
  const task = agv?.taskId ? tasks.find((t) => t.id === agv.taskId) : null

  if (!agv || !showAgvDetail) return null

  const color = statusColor(agv.status)

  return (
    <div className="modal-backdrop" onClick={() => setShowAgvDetail(false)}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal__header" style={{ borderTopColor: color }}>
          <div className="modal__title">
            <span className="modal__dot" style={{ background: color }} />
            {agv.id} · Vehicle Detail
          </div>
          <button className="modal__close" onClick={() => setShowAgvDetail(false)}>
            ✕
          </button>
        </div>

        <div className="modal__body">
          <div className="detail-grid">
            <div className="detail-item">
              <span className="detail-item__k">Status</span>
              <span className="detail-item__v" style={{ color }}>
                {agv.statusLabel}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-item__k">Battery</span>
              <span className="detail-item__v mono">{agv.battery.toFixed(1)}%</span>
            </div>
            <div className="detail-item">
              <span className="detail-item__k">Task</span>
              <span className="detail-item__v mono">{agv.taskId || 'none'}</span>
            </div>
            <div className="detail-item">
              <span className="detail-item__k">Distance</span>
              <span className="detail-item__v mono">
                {(agv.distanceM / 1000).toFixed(2)} km
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-item__k">Waypoint</span>
              <span className="detail-item__v mono">{agv.currentWp}</span>
            </div>
            <div className="detail-item">
              <span className="detail-item__k">Target</span>
              <span className="detail-item__v mono">{agv.targetWp || 'none'}</span>
            </div>
            <div className="detail-item">
              <span className="detail-item__k">Pickup / Drop-off</span>
              <span className="detail-item__v mono">
                {agv.pickupLoc || '-'} → {agv.dropoffLoc || '-'}
              </span>
            </div>
            <div className="detail-item">
              <span className="detail-item__k">Remaining Path</span>
              <span className="detail-item__v mono">
                {agv.path.length > 0 ? `${agv.path.length} steps` : 'none'}
              </span>
            </div>
          </div>

          <div className="modal__battery">
            <div
              className="modal__battery-bar"
              style={{
                width: `${Math.max(0, Math.min(100, agv.battery))}%`,
                background: agv.battery > 20 ? 'var(--accent-cyan)' : 'var(--accent-red)',
              }}
            />
          </div>

          {task && (
            <div className="modal__task">
              <span className="detail-item__k">Task Detail</span>
              <span className="mono">
                {task.id} · {task.type === 'import' ? 'Import' : 'Export'} ·{' '}
                {task.pickup_loc_id} → {task.dropoff_loc_id}
              </span>
            </div>
          )}

          <div className="modal__section-title">Vehicle Log</div>
          <div className="modal__log">
            {[...agv.log].reverse().map((line, idx) => (
              <div key={idx} className="modal__log-line">{line}</div>
            ))}
            {agv.log.length === 0 && <div className="dock-empty">No entries</div>}
          </div>
        </div>

        <div className="modal__footer">
          <button
            className="control-btn"
            onClick={() => { setSelectedAgv(null); setShowAgvDetail(false) }}
          >
            Clear Selection
          </button>
          <button
            className="control-btn control-btn--primary"
            onClick={() => setShowAgvDetail(false)}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}
