import { useMemo } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import type { AGVState, RiskInfo } from '../../stores/simulationStore'
import { riskColor, statusColor } from '../../theme'

const AGV_COLORS = [
  '#FF5733', '#007BFF', '#C70039', '#9B59B6',
  '#F1C40F', '#2ECC71', '#E74C3C', '#16A085',
]

const PADDING = 60
const ROAD_STROKE = 3
const AGV_SIZE = 16

const LANE_RE = /^(sl|ll)(\d+)_x(-?[\d.]+)_z(-?[\d.]+)$/

function areaStyle(areaNo: string): { stroke: string; fill: string } {
  if (areaNo.includes('QC_Area')) {
    return { stroke: '#D97216', fill: 'rgba(255, 133, 27, 0.16)' }
  }
  if (areaNo.includes('YARD_Area')) {
    return { stroke: '#208538', fill: 'rgba(40, 167, 69, 0.14)' }
  }
  if (areaNo.includes('Ship_Area')) {
    return { stroke: '#2b6cb0', fill: 'rgba(49, 130, 206, 0.14)' }
  }
  return { stroke: '#718096', fill: 'rgba(113, 128, 150, 0.12)' }
}

export function Map2D() {
  const {
    networkNodes, networkEdges, jobPoints, agvStates, risks,
    selectedAgvId, setSelectedAgv, setShowAgvDetail,
  } = useSimulationStore()

  const view = useMemo(() => {
    if (networkNodes.length === 0) return null
    let minX = Infinity, maxX = -Infinity
    let minZ = Infinity, maxZ = -Infinity
    const consider = (x: number, z: number) => {
      if (x < minX) minX = x
      if (x > maxX) maxX = x
      if (z < minZ) minZ = z
      if (z > maxZ) maxZ = z
    }
    networkNodes.forEach((n) => consider(n.position.x, n.position.z))
    Object.values(jobPoints).forEach((jp) => {
      consider(jp.pos.x - jp.width / 2, jp.pos.z - jp.height / 2)
      consider(jp.pos.x + jp.width / 2, jp.pos.z + jp.height / 2)
    })
    const width = maxX - minX + PADDING * 2
    const height = maxZ - minZ + PADDING * 2
    return {
      width,
      height,
      sx: (x: number) => x - minX + PADDING,

      sz: (z: number) => (maxZ - z) + PADDING,
    }
  }, [networkNodes, jobPoints])

  const lookup = useMemo(() => {
    const map = new Map<string, { x: number; z: number }>()
    networkNodes.forEach((n) => map.set(n.id, { x: n.position.x, z: n.position.z }))
    return map
  }, [networkNodes])

  const networkPath = useMemo(() => {
    if (!view || networkNodes.length === 0) return ''
    const seen = new Set<string>()
    const parts: string[] = []

    let laneXWidth = 0
    networkNodes.forEach((n) => {
      if ((n.id.startsWith('sl') || n.id.startsWith('ll'))
          && n.position.x > laneXWidth) {
        laneXWidth = n.position.x
      }
    })

    for (const edge of networkEdges) {
      const a = lookup.get(edge.from)
      const b = lookup.get(edge.to)
      if (!a || !b) continue

      const key = edge.from < edge.to
        ? `${edge.from}|${edge.to}`
        : `${edge.to}|${edge.from}`
      if (seen.has(key)) continue
      seen.add(key)

      const ma = LANE_RE.exec(edge.from)
      const mb = LANE_RE.exec(edge.to)
      if (ma && mb) {
        const sameType = ma[1] === mb[1]
        const sameX = ma[3] === mb[3]
        const adjacent = Math.abs(parseInt(ma[2], 10) - parseInt(mb[2], 10)) === 1
        const x = parseFloat(ma[3])
        if (sameType && sameX && adjacent && x > 0 && x < laneXWidth) continue
      }

      parts.push(`M${view.sx(a.x).toFixed(1)} ${view.sz(a.z).toFixed(1)}`
        + `L${view.sx(b.x).toFixed(1)} ${view.sz(b.z).toFixed(1)}`)
    }
    return parts.join('')
  }, [networkEdges, networkNodes, lookup, view])

  if (!view || networkNodes.length === 0) {
    return (
      <div className="map2d map2d--empty">
        <div className="map2d__empty-text">Waiting for network data…</div>
      </div>
    )
  }

  const agvColor = (id: string) => {
    const idx = parseInt(id.replace('AGV-', ''), 10) || 0
    return AGV_COLORS[idx % AGV_COLORS.length]
  }

  const toPoints = (wps: string[]): string =>
    wps
      .map((wp) => lookup.get(wp))
      .filter(Boolean)
      .map((p) => `${view.sx(p!.x).toFixed(1)},${view.sz(p!.z).toFixed(1)}`)
      .join(' ')

  return (
    <div className="map2d">
      <svg
        className="map2d__svg"
        viewBox={`0 0 ${view.width.toFixed(0)} ${view.height.toFixed(0)}`}
        preserveAspectRatio="xMidYMid meet"
      >

        <rect x={0} y={0} width={view.width} height={view.height} fill="#FAFBFC" />

        <path
          d={networkPath}
          stroke="rgba(110, 110, 110, 0.55)"
          strokeWidth={ROAD_STROKE}
          fill="none"
          strokeLinecap="round"
        />

        {Object.values(jobPoints).map((jp) => {
          const style = areaStyle(jp.areaNo)
          const x = view.sx(jp.pos.x - jp.width / 2)
          const y = view.sz(jp.pos.z + jp.height / 2)
          return (
            <g key={jp.id}>
              <rect
                x={x}
                y={y}
                width={jp.width}
                height={jp.height}
                fill={style.fill}
                stroke={style.stroke}
                strokeWidth={2}
              />
              <text
                x={x + jp.width / 2}
                y={y + jp.height / 2}
                textAnchor="middle"
                dominantBaseline="middle"
                className="map2d__area-label"
                fill={style.stroke}
              >
                {jp.bay}
              </text>
              <title>{`${jp.id}  (${jp.pos.x}, ${jp.pos.z})`}</title>
            </g>
          )
        })}

        {risks
          .filter((r) => r.type === 'TRAFFIC_CONGESTION'
            && (r.affectedWaypoints?.length ?? 0) > 0)
          .map((risk) => {
            const pts = (risk.affectedWaypoints || [])
              .map((wp) => lookup.get(wp))
              .filter(Boolean) as { x: number; z: number }[]
            if (pts.length === 0) return null
            const xs = pts.map((p) => view.sx(p.x))
            const zs = pts.map((p) => view.sz(p.z))
            const x0 = Math.min(...xs), x1 = Math.max(...xs)
            const y0 = Math.min(...zs), y1 = Math.max(...zs)
            return (
              <g key={risk.id}>
                <rect
                  x={x0} y={y0}
                  width={Math.max(x1 - x0, 3)}
                  height={Math.max(y1 - y0, 3)}
                  fill="rgba(128, 0, 128, 0.18)"
                  stroke="rgba(128, 0, 128, 0.65)"
                  strokeWidth={2}
                  strokeDasharray="6 4"
                />
                <text
                  x={(x0 + x1) / 2} y={(y0 + y1) / 2}
                  textAnchor="middle" dominantBaseline="middle"
                  className="map2d__risk-label"
                  fill="#6B2D8B"
                >
                  Congestion
                </text>
                <title>{risk.message}</title>
              </g>
            )
          })}

        {agvStates.map((agv: AGVState) => {
          const isSelected = selectedAgvId === agv.id
          const trail = toPoints(agv.historyPath || [])
          const route = toPoints(agv.path || [])
          const color = agvColor(agv.id)
          return (
            <g key={`${agv.id}-lines`}>
              {trail && (
                <polyline
                  points={trail}
                  fill="none"
                  stroke={color}
                  strokeWidth={isSelected ? 2.5 : 1.8}
                  strokeDasharray="5 5"
                  opacity={isSelected ? 0.7 : 0.38}
                />
              )}
              {route && (
                <polyline
                  points={route}
                  fill="none"
                  stroke={color}
                  strokeWidth={isSelected ? 5 : 3}
                  opacity={isSelected ? 0.95 : 0.55}
                  strokeLinejoin="round"
                />
              )}
            </g>
          )
        })}

        {agvStates.map((agv: AGVState) => {
          const isSelected = selectedAgvId === agv.id
          const half = (isSelected ? AGV_SIZE * 1.25 : AGV_SIZE) / 2
          const cx = view.sx(agv.position.x)
          const cy = view.sz(agv.position.z)
          const color = agvColor(agv.id)
          return (
            <g
              key={agv.id}
              className="map2d__agv"
              onClick={() => {
                setSelectedAgv(isSelected ? null : agv.id)
                setShowAgvDetail(!isSelected)
              }}
            >

              {agv.broken && (
                <circle
                  cx={cx} cy={cy} r={half * 2.4}
                  fill="none" stroke="#e53e3e" strokeWidth={3} opacity={0.7}
                />
              )}
              <rect
                x={cx - half} y={cy - half}
                width={half * 2} height={half * 2}
                fill={color}
                stroke={isSelected ? '#1a202c' : '#ffffff'}
                strokeWidth={isSelected ? 3 : 1.8}
                rx={2}
              />
              <text
                x={cx} y={cy}
                textAnchor="middle" dominantBaseline="central"
                className="map2d__agv-text"
              >
                {agv.id.replace('AGV-', '')}
              </text>
              <title>
                {`${agv.id}\nStatus: ${agv.statusLabel}\nBattery: ${agv.battery.toFixed(1)}%\n`
                  + `Task: ${agv.taskId || 'none'}\nWaypoint: ${agv.currentWp}\n`
                  + `Target: ${agv.targetWp || 'none'}\nRemaining: ${agv.path.length} steps`}
              </title>
            </g>
          )
        })}

        {risks
          .filter((r) => r.type !== 'TRAFFIC_CONGESTION' && r.position)
          .map((risk: RiskInfo) => {
            const cx = view.sx(risk.position!.x)
            const cy = view.sz(risk.position!.z)
            const color = riskColor(risk.type)
            return (
              <g key={risk.id}>
                <circle cx={cx} cy={cy} r={11} fill="none"
                        stroke={color} strokeWidth={3} opacity={0.85} />
                <circle cx={cx} cy={cy} r={4} fill={color} />
                <text x={cx + 15} y={cy + 4} className="map2d__risk-label"
                      fill={color}>
                  {risk.label}
                </text>
                <title>{risk.message}</title>
              </g>
            )
          })}
      </svg>

      <div className="map2d__legend">
        <div className="map2d__legend-title">Legend</div>
        <div className="map2d__legend-row">
          <span className="map2d__legend-swatch" style={{ background: '#D97216' }} />
          Quay Cranes
        </div>
        <div className="map2d__legend-row">
          <span className="map2d__legend-swatch" style={{ background: '#208538' }} />
          Yard Blocks
        </div>
        <div className="map2d__legend-row">
          <span className="map2d__legend-swatch" style={{ background: '#2b6cb0' }} />
          Vessels
        </div>
        <div className="map2d__legend-sep" />
        {(['FIRE', 'PERSONNEL_INTRUSION', 'TRAFFIC_CONGESTION',
           'AGV_FAILURE', 'NO_HELMET', 'SMOKING'] as const).map((t) => (
          <div className="map2d__legend-row" key={t}>
            <span className="map2d__legend-swatch"
                  style={{ background: riskColor(t) }} />
            {t === 'FIRE' ? 'Fire'
              : t === 'PERSONNEL_INTRUSION' ? 'Personnel Intrusion'
                : t === 'TRAFFIC_CONGESTION' ? 'Traffic Congestion'
                  : t === 'AGV_FAILURE' ? 'AGV Failure'
                    : t === 'NO_HELMET' ? 'No Helmet' : 'Smoking'}
          </div>
        ))}
      </div>

      <div className="map2d__statusbar">
        {agvStates.map((agv) => (
          <span key={agv.id} className="map2d__status-chip">
            <span className="map2d__status-dot"
                  style={{ background: statusColor(agv.status) }} />
            {agv.id} {agv.statusLabel}
          </span>
        ))}
      </div>
    </div>
  )
}
