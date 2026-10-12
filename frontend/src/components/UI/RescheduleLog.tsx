import { useEffect, useMemo, useRef, useState } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'

const METHOD_COLORS: Record<string, string> = {
  'A* replan': 'var(--accent-blue)',
  'A* planning': 'var(--accent-blue)',
  'Task reassigned': 'var(--accent-yellow)',
  'Manual': 'var(--accent-purple)',
  'API': 'var(--accent-cyan)',
  'Model service': 'var(--accent-cyan)',
  'Timeout': 'var(--text-tertiary)',
  'Event-triggered': 'var(--accent-red)',
}

export function RescheduleLog() {
  const { rescheduleLog } = useSimulationStore()
  const [onlyRisk, setOnlyRisk] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  const rows = useMemo(() => {
    const list = onlyRisk
      ? rescheduleLog.filter((e) =>
          /risk|block|fail|lock|conflict|collision/i.test(e.reason) ||
          e.agvId === 'AI' || e.agvId === 'SYS')
      : rescheduleLog
    return [...list].reverse()
  }, [rescheduleLog, onlyRisk])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = 0
  }, [rows.length])

  return (
    <div className="dock-panel">
      <div className="dock-panel__header">
        <span className="dock-panel__title">Reschedule Log</span>
        <span className="dock-panel__count">{rows.length}</span>
        <label className="dock-panel__filter">
          <input
            type="checkbox"
            checked={onlyRisk}
            onChange={(e) => setOnlyRisk(e.target.checked)}
          />
          Risk-related only
        </label>
      </div>

      <div className="dock-panel__body" ref={scrollRef}>
        {rows.length === 0 && (
          <div className="dock-empty">No reschedule events (fleet operating as planned)</div>
        )}
        {rows.map((entry) => (
          <div className="log-row" key={`${entry.seq}-${entry.time}`}>
            <span className="log-row__time">T{entry.time}</span>
            <span className="log-row__agv">{entry.agvId}</span>
            <span className="log-row__reason">{entry.reason}</span>
            <span
              className="log-row__method"
              style={{ color: METHOD_COLORS[entry.method] || 'var(--text-secondary)' }}
            >
              {entry.method}
            </span>
            <span className="log-row__result">{entry.result}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
