import { statusColor } from '../../theme'
import type { StatusCount } from '../../stores/simulationStore'

interface StatusDonutProps {
  data: StatusCount[]
  total: number
}

const SIZE = 132
const STROKE = 16
const RADIUS = (SIZE - STROKE) / 2
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

export function StatusDonut({ data, total }: StatusDonutProps) {
  const sum = data.reduce((acc, d) => acc + d.count, 0)
  let offset = 0

  return (
    <div className="donut-wrap">
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <g transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}>
          <circle
            cx={SIZE / 2}
            cy={SIZE / 2}
            r={RADIUS}
            fill="none"
            stroke="var(--bg-elevated)"
            strokeWidth={STROKE}
          />
          {sum > 0 && data.map((d) => {
            const fraction = d.count / sum
            const dash = fraction * CIRCUMFERENCE
            const el = (
              <circle
                key={d.status}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                stroke={statusColor(d.status)}
                strokeWidth={STROKE}
                strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
                strokeDashoffset={-offset}
              />
            )
            offset += dash
            return el
          })}
        </g>
        <text
          x="50%"
          y="47%"
          textAnchor="middle"
          dominantBaseline="middle"
          className="donut-center-value"
        >
          {total}
        </text>
        <text
          x="50%"
          y="62%"
          textAnchor="middle"
          dominantBaseline="middle"
          className="donut-center-label"
        >
          VEHICLES
        </text>
      </svg>

      <div className="donut-legend">
        {data.length === 0 && <div className="donut-legend__empty">No data</div>}
        {data.map((d) => (
          <div key={d.status} className="donut-legend__item">
            <span
              className="donut-legend__dot"
              style={{ background: statusColor(d.status) }}
            />
            <span className="donut-legend__label">{d.label}</span>
            <span className="donut-legend__count">{d.count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
