import { useMemo, useRef } from 'react'
import { useFrame } from '@react-three/fiber'
import { Html } from '@react-three/drei'
import * as THREE from 'three'
import { useSimulationStore } from '../../stores/simulationStore'
import type { RiskInfo } from '../../stores/simulationStore'
import { riskColor } from '../../theme'

const MARKER_ORDER = 999

function PulseRing({ color, radius = 26 }: { color: string; radius?: number }) {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((state) => {
    if (!ref.current) return
    const t = (state.clock.elapsedTime % 1.6) / 1.6
    const scale = 0.5 + t * 1.6
    ref.current.scale.set(scale, scale, scale)
    const mat = ref.current.material as THREE.MeshBasicMaterial
    mat.opacity = 0.55 * (1 - t)
  })
  return (
    <mesh ref={ref} rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.6, 0]}
          renderOrder={MARKER_ORDER}>
      <ringGeometry args={[radius * 0.8, radius, 40]} />
      <meshBasicMaterial color={color} transparent opacity={0.5}
                         side={THREE.DoubleSide} depthWrite={false}
                         depthTest={false} />
    </mesh>
  )
}

function FireMarker({ color }: { color: string }) {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((state) => {
    if (!ref.current) return
    const s = 1 + Math.sin(state.clock.elapsedTime * 6) * 0.12
    ref.current.scale.set(s, 1 + Math.sin(state.clock.elapsedTime * 5) * 0.25, s)
  })
  return (
    <group>
      <mesh ref={ref} position={[0, 30, 0]} renderOrder={MARKER_ORDER}>
        <coneGeometry args={[13, 60, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.5}
                           depthWrite={false} depthTest={false} />
      </mesh>
      <PulseRing color={color} radius={30} />
    </group>
  )
}

function SmokeMarker({ color }: { color: string }) {
  const ref = useRef<THREE.Group>(null)
  useFrame((state) => {
    if (!ref.current) return
    ref.current.rotation.y = state.clock.elapsedTime * 0.6
    ref.current.position.y = 24 + Math.sin(state.clock.elapsedTime * 1.5) * 4
  })
  return (
    <group>
      <group ref={ref}>
        {[[0, 0, 0, 11], [9, 5, 4, 8], [-8, 7, -5, 9], [3, 11, -7, 7]].map(
          (p, i) => (
            <mesh key={i} position={[p[0], p[1], p[2]]}
                  renderOrder={MARKER_ORDER}>
              <sphereGeometry args={[p[3], 14, 14]} />
              <meshBasicMaterial color={color} transparent opacity={0.3}
                                 depthWrite={false} depthTest={false} />
            </mesh>
          ),
        )}
      </group>
      <PulseRing color={color} radius={22} />
    </group>
  )
}

function HelmetMarker({ color }: { color: string }) {
  const ref = useRef<THREE.Mesh>(null)
  useFrame((state) => {
    if (!ref.current) return
    ref.current.rotation.y = state.clock.elapsedTime * 1.2
  })
  return (
    <group>
      <mesh ref={ref} position={[0, 26, 0]} renderOrder={MARKER_ORDER}>
        <octahedronGeometry args={[13, 0]} />
        <meshBasicMaterial color={color} transparent opacity={0.85}
                           depthWrite={false} depthTest={false} />
      </mesh>
      <PulseRing color={color} radius={24} />
    </group>
  )
}

function IntrusionMarker({ color }: { color: string }) {
  return (
    <group renderOrder={MARKER_ORDER}>

      <mesh position={[0, 30, 0]} renderOrder={MARKER_ORDER}>
        <sphereGeometry args={[5.5, 16, 16]} />
        <meshBasicMaterial color={color} transparent opacity={0.95}
                           depthWrite={false} depthTest={false} />
      </mesh>

      <mesh position={[0, 17, 0]} renderOrder={MARKER_ORDER}>
        <capsuleGeometry args={[3.6, 12, 6, 12]} />
        <meshBasicMaterial color={color} transparent opacity={0.9}
                           depthWrite={false} depthTest={false} />
      </mesh>
      <PulseRing color={color} radius={34} />
    </group>
  )
}

function RiskMarker({ risk }: { risk: RiskInfo }) {
  const color = riskColor(risk.type)
  const pos = risk.position
  if (!pos) return null

  return (
    <group position={[pos.x, 0, pos.z]}>
      {risk.type === 'FIRE' && <FireMarker color={color} />}
      {risk.type === 'SMOKING' && <SmokeMarker color={color} />}
      {risk.type === 'NO_HELMET' && <HelmetMarker color={color} />}
      {risk.type === 'PERSONNEL_INTRUSION' && <IntrusionMarker color={color} />}

      <Html center position={[0, 52, 0]} distanceFactor={420}
            style={{ pointerEvents: 'none' }}>
        <div className="risk-tag" style={{ ['--risk-color' as string]: color }}>
          <span className="risk-tag__dot" />
          {risk.label}
          {risk.affectedCount > 0 && (
            <span className="risk-tag__meta">{risk.affectedCount} blocked</span>
          )}
        </div>
      </Html>
    </group>
  )
}

function CongestionZone({ risk }: { risk: RiskInfo }) {
  const { networkNodes } = useSimulationStore()

  const bounds = useMemo(() => {
    const wps = risk.affectedWaypoints || []
    if (wps.length === 0) return null
    const lookup = new Map(networkNodes.map((n) => [n.id, n.position]))
    let minX = Infinity, maxX = -Infinity
    let minZ = Infinity, maxZ = -Infinity
    let found = 0
    for (const wp of wps) {
      const p = lookup.get(wp)
      if (!p) continue
      found++
      minX = Math.min(minX, p.x); maxX = Math.max(maxX, p.x)
      minZ = Math.min(minZ, p.z); maxZ = Math.max(maxZ, p.z)
    }
    if (found === 0) return null
    return { minX, maxX, minZ, maxZ, found }
  }, [risk.affectedWaypoints, networkNodes])

  if (!bounds || !risk.position) return null

  const width = Math.max(30, bounds.maxX - bounds.minX + 40)
  const depth = Math.max(30, bounds.maxZ - bounds.minZ + 40)
  const cx = (bounds.minX + bounds.maxX) / 2
  const cz = (bounds.minZ + bounds.maxZ) / 2
  const color = riskColor(risk.type)

  return (
    <group>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[cx, 1.2, cz]}>
        <planeGeometry args={[width, depth]} />
        <meshBasicMaterial color={color} transparent opacity={0.22}
                           side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
      <lineSegments position={[cx, 1.4, cz]}>
        <edgesGeometry args={[new THREE.BoxGeometry(width, 0.1, depth)]} />
        <lineBasicMaterial color={color} />
      </lineSegments>
      <RiskMarker risk={risk} />
    </group>
  )
}

export function RiskLayer() {
  const { risks, networkNodes } = useSimulationStore()

  const visible = risks.filter((r) => r.position || r.type === 'AGV_FAILURE')
  if (visible.length === 0) return null

  return (
    <group name="risk-layer">
      {visible.map((risk) =>
        risk.type === 'TRAFFIC_CONGESTION' && networkNodes.length > 0 ? (
          <CongestionZone key={risk.id} risk={risk} />
        ) : risk.type === 'TRAFFIC_CONGESTION' ? null : (
          <RiskMarker key={risk.id} risk={risk} />
        ),
      )}
    </group>
  )
}
