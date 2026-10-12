import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html, Billboard, Line } from '@react-three/drei'
import * as THREE from 'three'
import { useSimulationStore } from '../../stores/simulationStore'
import type { AGVState } from '../../stores/simulationStore'
import { statusColor } from '../../theme'

const DESIGN_SYSTEM = {
  body: {
    primary: '#2d3540',
    secondary: '#3a4550',
    wheel: '#1a2028',
    accent: '#4a5560',
  },
  label: {
    bg: '#ffffff',
    border: '#d0d5dd',
    text: '#4a5568',
  },
  panel: {
    bg: 'rgba(255, 255, 255, 0.98)',
    border: '#d0d5dd',
    text: '#1a202c',
    textMuted: '#4a5568',
    textTertiary: '#718096',
  },
}

const SMOOTH_CONFIG = {
  positionLerpSpeed: 6,
  rotationLerpSpeed: 15,
  minMoveThreshold: 0.1,
}

function HtmlLabel({ text, color, isSelected }: { text: string; color: string; isSelected: boolean }) {
  const borderColor = isSelected ? color : DESIGN_SYSTEM.label.border
  const textColor = isSelected ? color : '#1a202c'

  return (
    <Billboard position={[0, 12, 0]}>
      <Html center distanceFactor={100} style={{ pointerEvents: 'none' }}>
        <div style={{
          background: DESIGN_SYSTEM.label.bg,
          border: `1.5px solid ${borderColor}`,
          borderRadius: '4px',
          padding: '4px 10px',
          fontSize: '11px',
          fontFamily: 'JetBrains Mono, SF Mono, Consolas, monospace',
          fontWeight: isSelected ? '600' : '500',
          color: textColor,
          whiteSpace: 'nowrap',
          boxShadow: '0 2px 8px rgba(0,0,0,0.12)',
          letterSpacing: '0.5px',
        }}>
          {text}
        </div>
      </Html>
    </Billboard>
  )
}

function AGV({
  agv,
  isSelected,
}: {
  agv: AGVState
  isSelected: boolean
}) {
  const positionRef = useRef<THREE.Group>(null)
  const rotationRef = useRef<THREE.Group>(null)
  const bodyRef = useRef<THREE.Mesh>(null)

  const targetPosition = useRef(new THREE.Vector3(agv.position.x, 5, agv.position.z))
  const currentPosition = useRef(new THREE.Vector3(agv.position.x, 5, agv.position.z))
  const currentRotation = useRef(agv.rotation)

  const setSelectedAgv = useSimulationStore((s) => s.setSelectedAgv)
  const setShowAgvDetail = useSimulationStore((s) => s.setShowAgvDetail)

  const color = statusColor(agv.status)

  useFrame((state, delta) => {
    if (!positionRef.current || !rotationRef.current) return

    const clampedDelta = Math.min(delta, 0.1)

    if (Math.abs(targetPosition.current.x - agv.position.x) >
          SMOOTH_CONFIG.minMoveThreshold ||
        Math.abs(targetPosition.current.z - agv.position.z) >
          SMOOTH_CONFIG.minMoveThreshold) {
      targetPosition.current.set(agv.position.x, 5, agv.position.z)
    }

    const posLerpFactor = 1 - Math.pow(0.001, clampedDelta * SMOOTH_CONFIG.positionLerpSpeed)
    if (currentPosition.current.distanceToSquared(targetPosition.current) < 0.001) {
      currentPosition.current.copy(targetPosition.current)
    } else {
      currentPosition.current.lerp(targetPosition.current, posLerpFactor)
    }
    positionRef.current.position.copy(currentPosition.current)

    const targetY = agv.rotation
    let diff = targetY - currentRotation.current
    while (diff > Math.PI) diff -= Math.PI * 2
    while (diff < -Math.PI) diff += Math.PI * 2
    if (Math.abs(diff) > Math.PI / 2) {
      diff = diff > 0 ? diff - Math.PI : diff + Math.PI
    }
    if (Math.abs(diff) > 0.001) {
      currentRotation.current += diff * clampedDelta * SMOOTH_CONFIG.rotationLerpSpeed
      if (currentRotation.current > Math.PI * 2) currentRotation.current -= Math.PI * 2
      if (currentRotation.current < -Math.PI * 2) currentRotation.current += Math.PI * 2
    }
    rotationRef.current.rotation.y = currentRotation.current

    if (bodyRef.current && agv.broken) {
      const mat = bodyRef.current.material as THREE.MeshStandardMaterial
      mat.emissiveIntensity = 0.35 + Math.abs(Math.sin(state.clock.elapsedTime * 4)) * 0.55
    }

    positionRef.current.updateMatrixWorld()
  })

  const agvNumber = agv.id.replace('AGV-', '')

  return (
    <group ref={positionRef} position={[agv.position.x, 5, agv.position.z]}>
      <group ref={rotationRef} rotation={[0, agv.rotation, 0]}>
        <mesh
          ref={bodyRef}
          onClick={(e) => {
            e.stopPropagation()
            if (isSelected) {
              setSelectedAgv(null)
              setShowAgvDetail(false)
            } else {
              setSelectedAgv(agv.id)
              setShowAgvDetail(true)
            }
          }}
        >
          <boxGeometry args={[12, 4, 20]} />
          <meshStandardMaterial
            color={agv.broken ? '#8b1a1a' : DESIGN_SYSTEM.body.primary}
            emissive={agv.broken ? '#e53e3e' : '#000000'}
            emissiveIntensity={agv.broken ? 0.5 : 0}
            roughness={0.6}
            metalness={0.3}
          />
        </mesh>

        <mesh position={[0, 2.3, 0]}>
          <boxGeometry args={[10, 0.5, 18]} />
          <meshStandardMaterial
            color={color}
            emissive={color}
            emissiveIntensity={isSelected ? 0.7 : 0.5}
            roughness={0.4}
          />
        </mesh>

        <mesh position={[0, 0.5, 10.5]}>
          <boxGeometry args={[8, 1.2, 0.6]} />
          <meshStandardMaterial color={color} emissive={color}
                                emissiveIntensity={0.4} roughness={0.5} />
        </mesh>
        <mesh position={[0, 0.5, -10.5]}>
          <boxGeometry args={[8, 1.2, 0.6]} />
          <meshStandardMaterial color={color} emissive={color}
                                emissiveIntensity={0.4} roughness={0.5} />
        </mesh>

        {[[-5, -1.5, 8], [5, -1.5, 8], [-5, -1.5, -8], [5, -1.5, -8]].map((pos, i) => (
          <mesh key={i} position={pos as [number, number, number]}
                rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[2.5, 2.5, 2, 16]} />
            <meshStandardMaterial color={DESIGN_SYSTEM.body.wheel} roughness={0.85} />
          </mesh>
        ))}
        {[[-5, -1.5, 8], [5, -1.5, 8], [-5, -1.5, -8], [5, -1.5, -8]].map((pos, i) => (
          <mesh key={`hub-${i}`} position={pos as [number, number, number]}
                rotation={[0, 0, Math.PI / 2]}>
            <cylinderGeometry args={[1.2, 1.2, 2.2, 12]} />
            <meshStandardMaterial color={DESIGN_SYSTEM.body.accent}
                                  roughness={0.6} metalness={0.3} />
          </mesh>
        ))}
      </group>

      <HtmlLabel text={`AGV-${agvNumber}`} color={color} isSelected={isSelected} />

      {isSelected && (
        <Html position={[30, 8, 0]} distanceFactor={220}
              style={{ pointerEvents: 'none' }}>
          <div style={{
            background: DESIGN_SYSTEM.panel.bg,
            border: `1px solid ${DESIGN_SYSTEM.panel.border}`,
            color: DESIGN_SYSTEM.panel.text,
            padding: '10px 14px',
            borderRadius: '5px',
            fontSize: '11px',
            fontFamily: 'Inter, -apple-system, sans-serif',
            minWidth: '150px',
            boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          }}>
            <div style={{
              fontFamily: 'JetBrains Mono, monospace',
              fontWeight: '600',
              marginBottom: '8px',
              color,
              fontSize: '12px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}>
              <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: color }} />
              {agv.id}
            </div>
            <div className="agv-tip-row">
              <span>Status</span><span>{agv.statusLabel}</span>
            </div>
            <div className="agv-tip-row">
              <span>Battery</span><span>{agv.battery.toFixed(1)}%</span>
            </div>
            <div className="agv-tip-row">
              <span>Task</span><span>{agv.taskId || 'none'}</span>
            </div>
            <div className="agv-tip-row">
              <span>Path</span><span>{agv.path.length} steps</span>
            </div>
          </div>
        </Html>
      )}
    </group>
  )
}

export function AGVFleet({ agvs, selectedId }: { agvs: AGVState[]; selectedId: string | null }) {
  const { networkNodes } = useSimulationStore()

  const lookup = useMemo(() => {
    const map = new Map<string, { x: number; y: number; z: number }>()
    networkNodes.forEach((n) => map.set(n.id, n.position))
    return map
  }, [networkNodes])

  if (agvs.length === 0) return null

  const toPoints = (wps: string[], height: number): [number, number, number][] =>
    (wps || [])
      .map((wp) => lookup.get(wp))
      .filter((p): p is { x: number; y: number; z: number } => !!p)
      .map((p) => [p.x, height, p.z])

  return (
    <group>

      <group name="agv-routes">
        {agvs.map((agv) => {
          const isSelected = selectedId === agv.id
          const color = statusColor(agv.status)
          const routePoints = toPoints(agv.path || [], 2.6)
          const trailPoints = toPoints(agv.historyPath || [], 1.8)
          return (
            <group key={`${agv.id}-lines`}>
              {routePoints.length > 1 && (
                <Line
                  points={routePoints}
                  color={color}
                  lineWidth={isSelected ? 2.6 : 1.1}
                  transparent
                  opacity={isSelected ? 0.95 : 0.5}
                />
              )}
              {trailPoints.length > 1 && (
                <Line
                  points={trailPoints}
                  color={color}
                  lineWidth={isSelected ? 1.3 : 0.7}
                  dashed
                  dashSize={8}
                  gapSize={6}
                  transparent
                  opacity={isSelected ? 0.55 : 0.28}
                />
              )}
            </group>
          )
        })}
      </group>

      <group name="agv-fleet">
        {agvs.map((agv) => (
          <AGV
            key={agv.id}
            agv={agv}
            isSelected={selectedId === agv.id}
          />
        ))}
      </group>
    </group>
  )
}
