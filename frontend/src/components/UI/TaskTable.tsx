import { useMemo, useState } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import type { TaskInfo } from '../../stores/simulationStore'

const STATUS_STYLE: Record<string, { label: string; bg: string; fg: string }> = {
  PENDING: { label: 'Pending', bg: 'rgba(214, 158, 46, 0.14)', fg: '#8a6d1f' },
  ASSIGNED: { label: 'Running', bg: 'rgba(49, 130, 206, 0.14)', fg: '#2b6cb0' },
  COMPLETED: { label: 'Done', bg: 'rgba(56, 161, 105, 0.14)', fg: '#276749' },
  FAILED: { label: 'Failed', bg: 'rgba(229, 62, 62, 0.14)', fg: '#9b2c2c' },
}

type Filter = 'ALL' | 'PENDING' | 'ASSIGNED' | 'COMPLETED'

const FILTERS: { key: Filter; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'PENDING', label: 'Pending' },
  { key: 'ASSIGNED', label: 'Running' },
  { key: 'COMPLETED', label: 'Done' },
]

const shortLoc = (loc: string | null | undefined): string => {
  if (!loc) return '-'
  return loc
    .replace('YARD_Area_', 'Y')
    .replace('QC_Area_', '')
    .replace('Ship_Area_', 'S')
}

export function TaskTable() {
  const { tasks, selectedAgvId, setSelectedAgv } = useSimulationStore()
  const [filter, setFilter] = useState<Filter>('ALL')

  const rows = useMemo(() => {
    const list = filter === 'ALL'
      ? tasks
      : tasks.filter((t) => t.status === filter)
    return list
  }, [tasks, filter])

  const counts = useMemo(() => {
    const out: Record<string, number> = { ALL: tasks.length }
    tasks.forEach((t) => { out[t.status] = (out[t.status] || 0) + 1 })
    return out
  }, [tasks])

  const duration = (t: TaskInfo): string => {
    if (t.assigned_time === null) return '-'
    const end = t.completed_time ?? null
    return end === null ? 'running' : `${end - t.assigned_time}`
  }

  return (
    <div className="dock-panel">
      <div className="dock-panel__header">
        <span className="dock-panel__title">Task Queue</span>
        <span className="dock-panel__count">{rows.length} / {tasks.length}</span>
        <div className="dock-panel__tabs">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              className={`chip ${filter === f.key ? 'chip--active' : ''}`}
              onClick={() => setFilter(f.key)}
            >
              {f.label}
              <span className="chip__count">{counts[f.key] || 0}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="dock-panel__body">
        <table className="data-table">
          <thead>
            <tr>
              <th>Task</th>
              <th>Type</th>
              <th>Status</th>
              <th>AGV</th>
              <th>Pickup</th>
              <th>Drop-off</th>
              <th>Time</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && (
              <tr><td colSpan={7} className="data-table__empty">No tasks</td></tr>
            )}
            {rows.map((t) => {
              const style = STATUS_STYLE[t.status] || STATUS_STYLE.PENDING
              const isMine = !!selectedAgvId && t.assigned_agv_id === selectedAgvId
              return (
                <tr
                  key={t.id}
                  className={isMine ? 'data-table__row--active' : ''}
                  onClick={() => t.assigned_agv_id && setSelectedAgv(t.assigned_agv_id)}
                >
                  <td className="mono">{t.id.replace('Task-', '#')}</td>
                  <td>{t.type === 'import' ? 'Import' : 'Export'}</td>
                  <td>
                    <span className="status-pill"
                          style={{ background: style.bg, color: style.fg }}>
                      {style.label}
                    </span>
                  </td>
                  <td className="mono">{t.assigned_agv_id || '-'}</td>
                  <td className="mono">{shortLoc(t.pickup_loc_id)}</td>
                  <td className="mono">{shortLoc(t.dropoff_loc_id)}</td>
                  <td className="mono">{duration(t)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
