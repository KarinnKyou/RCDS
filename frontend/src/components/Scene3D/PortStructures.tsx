import { useMemo } from 'react'
import { Html } from '@react-three/drei'
import * as THREE from 'three'
import { useSimulationStore } from '../../stores/simulationStore'

const ROAD_Z_STEP = 25
const APRON_DEPTH = 80

const DESIGN_SYSTEM = {
  equipment: {
    qc: {
      structure: '#2d3540',
      accent: '#3a4550',
      warning: '#e07030',
      beacon: '#ff8040',
    },
    rtg: {
      structure: '#3a4550',
      accent: '#d4a020',
      cabin: '#2d3540',
    },
    metal: '#252d35',
    wheel: '#1a2028',
    glass: '#4080c0',
  },

  container: [
    '#d04040', '#3070c0', '#30a060', '#e0a020',
    '#8050b0', '#20a0a0', '#e07030', '#60b030',
  ],

  surfaces: {
    yard: '#a0a8b0',
    yardBorder: '#707880',
    apron: '#a0a8b0',
    apronLine: '#f0b020',
  },

  ship: {
    hull: '#252d35',
    deck: '#303840',
    superstructure: '#3a4248',
    funnel: '#d04040',
  },

  label: {
    bg: 'rgba(255, 255, 255, 0.95)',
    border: '#d0d5dd',
    text: '#4a5568',
    textEmphasis: '#1a202c',
  }
}

function seededRandom(seed: number): number {
  const x = Math.sin(seed * 12.9898 + 78.233) * 43758.5453
  return x - Math.floor(x)
}

function QCApron({ width, centerX, z }: { width: number, centerX: number, z: number }) {
  const depth = APRON_DEPTH

  return (
    <group position={[centerX, 0.02, z]}>

      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[width, depth]} />
        <meshStandardMaterial
          color={DESIGN_SYSTEM.surfaces.apron}
          roughness={0.9}
          metalness={0.1}
        />
      </mesh>
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.01, depth / 2 - 2]}>
        <planeGeometry args={[width, 2]} />
        <meshBasicMaterial color={DESIGN_SYSTEM.surfaces.apronLine} />
      </mesh>
    </group>
  )
}

function QCCrane({ position, id }: { position: [number, number, number]; id: string }) {
  const [x, y, z] = position
  const style = DESIGN_SYSTEM.equipment.qc

  const legHeight = 85
  const gaugeZ = 75
  const gantryWidthX = 25
  const legThickness = 2.5
  const beamHeight = 4
  const beamWidth = 2
  const roadSideLength = 175
  const seaSideLength = 20

  const totalBeamLength = roadSideLength + gaugeZ + seaSideLength
  const beamCenterZ = (seaSideLength - roadSideLength) / 2

  return (
    <group position={[x, y, z]}>

      <group>

        <mesh position={[-gantryWidthX/2, legHeight/2, gaugeZ/2]}>
          <boxGeometry args={[legThickness, legHeight, legThickness]} />
          <meshStandardMaterial color={style.structure} roughness={0.6} metalness={0.35} />
        </mesh>

        <mesh position={[gantryWidthX/2, legHeight/2, gaugeZ/2]}>
          <boxGeometry args={[legThickness, legHeight, legThickness]} />
          <meshStandardMaterial color={style.structure} roughness={0.6} metalness={0.35} />
        </mesh>

        <mesh position={[-gantryWidthX/2, legHeight/2, -gaugeZ/2]}>
          <boxGeometry args={[legThickness, legHeight, legThickness]} />
          <meshStandardMaterial color={style.structure} roughness={0.6} metalness={0.35} />
        </mesh>

        <mesh position={[gantryWidthX/2, legHeight/2, -gaugeZ/2]}>
          <boxGeometry args={[legThickness, legHeight, legThickness]} />
          <meshStandardMaterial color={style.structure} roughness={0.6} metalness={0.35} />
        </mesh>
      </group>

      <group>

        <mesh position={[0, 1, gaugeZ/2]}>
          <boxGeometry args={[gantryWidthX + legThickness, 2, legThickness + 1]} />
          <meshStandardMaterial color={style.accent} />
        </mesh>

        <mesh position={[0, 1, -gaugeZ/2]}>
          <boxGeometry args={[gantryWidthX + legThickness, 2, legThickness + 1]} />
          <meshStandardMaterial color={style.accent} />
        </mesh>
      </group>

      <group position={[0, legHeight + beamHeight/2, beamCenterZ]}>

        <mesh position={[-gantryWidthX/2, 0, 0]}>
          <boxGeometry args={[beamWidth, beamHeight, totalBeamLength]} />
          <meshStandardMaterial color={style.structure} roughness={0.6} metalness={0.35} />
        </mesh>

        <mesh position={[gantryWidthX/2, 0, 0]}>
          <boxGeometry args={[beamWidth, beamHeight, totalBeamLength]} />
          <meshStandardMaterial color={style.structure} roughness={0.6} metalness={0.35} />
        </mesh>

        <mesh position={[0, 0, totalBeamLength/2 - beamWidth/2]}>
          <boxGeometry args={[gantryWidthX + beamWidth, beamHeight, beamWidth]} />
          <meshStandardMaterial color={style.structure} />
        </mesh>

        <mesh position={[0, 0, -totalBeamLength/2 + beamWidth/2]}>
          <boxGeometry args={[gantryWidthX + beamWidth, beamHeight, beamWidth]} />
          <meshStandardMaterial color={style.structure} />
        </mesh>

        <group position={[0, beamHeight/2 + 1, -80]}>

          <mesh>
            <boxGeometry args={[gantryWidthX + 2, 2, 8]} />
            <meshStandardMaterial color={style.accent} />
          </mesh>
          <mesh position={[0, 2, 0]}>
            <boxGeometry args={[8, 3, 6]} />
            <meshStandardMaterial color={DESIGN_SYSTEM.equipment.rtg.cabin} />
          </mesh>
          <mesh position={[0, -20, 0]}>
             <cylinderGeometry args={[0.1, 0.1, 40]} />
             <meshBasicMaterial color="#222" />
          </mesh>
          <mesh position={[0, -40, 0]}>
            <boxGeometry args={[20, 1, 8]} />
            <meshStandardMaterial color={style.warning} />
          </mesh>
        </group>

      </group>

      <Html position={[0, legHeight + 15, 0]} center distanceFactor={250}>
        <div style={{
          background: DESIGN_SYSTEM.label.bg,
          border: `1px solid ${DESIGN_SYSTEM.label.border}`,
          color: DESIGN_SYSTEM.label.textEmphasis,
          padding: '5px 14px',
          borderRadius: '3px',
          fontSize: '12px',
          fontFamily: 'JetBrains Mono, monospace',
          fontWeight: '600',
          letterSpacing: '0.5px',
          boxShadow: '0 2px 6px rgba(0,0,0,0.12)',
          whiteSpace: 'nowrap',
        }}>
          {id}
        </div>
      </Html>
    </group>
  )
}

function RTGCrane({ position, spanWidth, id }: {
  position: [number, number, number]
  spanWidth: number
  id: string
}) {
  const [x, y, z] = position
  const style = DESIGN_SYSTEM.equipment.rtg
  const legHeight = 45
  const beamHeight = 6
  const legWidth = 5

  return (
    <group position={[x, y, z]}>
      <mesh position={[-spanWidth/2, legHeight/2, 0]}>
        <boxGeometry args={[legWidth, legHeight, legWidth]} />
        <meshStandardMaterial color={style.structure} roughness={0.55} metalness={0.35} />
      </mesh>
      <mesh position={[spanWidth/2, legHeight/2, 0]}>
        <boxGeometry args={[legWidth, legHeight, legWidth]} />
        <meshStandardMaterial color={style.structure} roughness={0.55} metalness={0.35} />
      </mesh>
      <mesh position={[0, legHeight + beamHeight/2, 0]}>
        <boxGeometry args={[spanWidth + legWidth, beamHeight, 8]} />
        <meshStandardMaterial color={style.structure} roughness={0.55} metalness={0.35} />
      </mesh>
      <mesh position={[0, legHeight + beamHeight + 0.75, 0]}>
        <boxGeometry args={[spanWidth + legWidth, 1.5, 8.5]} />
        <meshStandardMaterial color={style.accent} roughness={0.5} />
      </mesh>
      <mesh position={[0, legHeight + beamHeight + 3.5, 0]}>
        <boxGeometry args={[15, 5, 6]} />
        <meshStandardMaterial color={style.cabin} roughness={0.6} metalness={0.3} />
      </mesh>
      <mesh position={[0, legHeight + beamHeight + 4, 3.2]}>
        <boxGeometry args={[12, 3, 0.3]} />
        <meshStandardMaterial
          color={DESIGN_SYSTEM.equipment.glass}
          transparent
          opacity={0.7}
          roughness={0.2}
          metalness={0.5}
        />
      </mesh>
      <mesh position={[0, legHeight - 8, 0]}>
        <boxGeometry args={[12, 3, 12]} />
        <meshStandardMaterial color={DESIGN_SYSTEM.equipment.metal} roughness={0.5} metalness={0.4} />
      </mesh>
      {[-spanWidth/2, spanWidth/2].map((xPos, i) => (
        <group key={`wheel-${i}`} position={[xPos, 2, 0]}>
          <mesh rotation={[Math.PI/2, 0, 0]}>
            <cylinderGeometry args={[2.5, 2.5, 6, 12]} />
            <meshStandardMaterial color={DESIGN_SYSTEM.equipment.wheel} roughness={0.85} />
          </mesh>
        </group>
      ))}
      <Html position={[0, legHeight + beamHeight + 14, 0]} center distanceFactor={200}>
        <div style={{
          background: DESIGN_SYSTEM.label.bg,
          border: `1px solid ${DESIGN_SYSTEM.label.border}`,
          color: DESIGN_SYSTEM.label.text,
          padding: '4px 10px',
          borderRadius: '3px',
          fontSize: '11px',
          fontFamily: 'JetBrains Mono, monospace',
          fontWeight: '500',
          boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
          whiteSpace: 'nowrap',
        }}>
          {id}
        </div>
      </Html>
    </group>
  )
}

function YardArea({ position, width, depth, id, laneOffsets, seed }: {
  position: [number, number, number]
  width: number
  depth: number
  id: string
  laneOffsets: number[]
  seed: number
}) {
  const [x, y, z] = position
  const colors = DESIGN_SYSTEM.container

  const containers = useMemo(() => {
    const result: Array<{ x: number; z: number; layer: number; color: string }> = []
    const containersPerLane = 5
    const containerSpacingZ = 22

    laneOffsets.forEach((laneX, laneIdx) => {
      for (let row = 0; row < containersPerLane; row++) {
        const layerSeed = seed + laneIdx * 100 + row
        const layers = Math.floor(seededRandom(layerSeed) * 3) + 1
        for (let layer = 0; layer < layers; layer++) {
          result.push({
            x: laneX,
            z: -depth/2 + 15 + row * containerSpacingZ,
            layer,
            color: colors[(laneIdx + row + layer) % colors.length]
          })
        }
      }
    })
    return result
  }, [laneOffsets, depth, seed, colors])

  return (
    <group position={[x, y, z]}>

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.2, 0]}>
        <planeGeometry args={[width, depth]} />
        <meshStandardMaterial
          color={DESIGN_SYSTEM.surfaces.yard}
          roughness={0.88}
          metalness={0.05}
        />
      </mesh>
      <lineSegments rotation={[-Math.PI / 2, 0, 0]} position={[0, 0.4, 0]}>
        <edgesGeometry args={[new THREE.PlaneGeometry(width, depth)]} />
        <lineBasicMaterial color={DESIGN_SYSTEM.surfaces.yardBorder} />
      </lineSegments>
      {containers.map((container, i) => (
        <mesh key={i} position={[container.x, 4 + container.layer * 8.5, container.z]}>
          <boxGeometry args={[8, 8, 20]} />
          <meshStandardMaterial color={container.color} roughness={0.6} metalness={0.2} />
        </mesh>
      ))}
      <Html position={[0, 32, 0]} center distanceFactor={200}>
        <div style={{
          background: DESIGN_SYSTEM.label.bg,
          border: `1px solid ${DESIGN_SYSTEM.label.border}`,
          color: DESIGN_SYSTEM.label.text,
          padding: '4px 12px',
          borderRadius: '3px',
          fontSize: '11px',
          fontFamily: 'JetBrains Mono, monospace',
          fontWeight: '500',
          boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
          whiteSpace: 'nowrap',
        }}>
          {id}
        </div>
      </Html>
    </group>
  )
}

function Ship({ position, id, seed }: { position: [number, number, number]; id: string; seed: number }) {
  const [x, y, z] = position
  const style = DESIGN_SYSTEM.ship
  const colors = DESIGN_SYSTEM.container
  const shipLength = 320
  const shipWidth = 55

  const containers = useMemo(() => {
    const result: Array<{ x: number; z: number; layer: number; color: string }> = []
    const spacingX = 8.5
    const spacingZ = 20.5
    const startX = -shipLength/2 + 60
    const endX = shipLength/2 - 20
    const colsX = Math.floor((endX - startX) / spacingX)
    const rowsZ = 2

    for (let col = 0; col < colsX; col++) {
      for (let row = 0; row < rowsZ; row++) {
        const layerSeed = seed + col * 100 + row
        const layers = Math.floor(seededRandom(layerSeed) * 4) + 2
        for (let layer = 0; layer < layers; layer++) {
          result.push({
            x: startX + col * spacingX,
            z: (row - 0.5) * spacingZ,
            layer,
            color: colors[(col + row + layer) % colors.length]
          })
        }
      }
    }
    return result
  }, [seed, colors])

  return (
    <group position={[x, y, z]}>
      <mesh position={[0, 14, 0]}>
        <boxGeometry args={[shipLength, 26, shipWidth]} />
        <meshStandardMaterial color={style.hull} roughness={0.65} metalness={0.35} />
      </mesh>
      <mesh position={[0, 2, 0]}>
        <boxGeometry args={[shipLength, 8, shipWidth - 10]} />
        <meshStandardMaterial color={style.hull} roughness={0.65} metalness={0.35} />
      </mesh>
      <mesh position={[shipLength/2 + 12, 14, 0]}>
        <boxGeometry args={[25, 26, shipWidth - 10]} />
        <meshStandardMaterial color={style.hull} roughness={0.65} metalness={0.35} />
      </mesh>
      <mesh position={[-shipLength/2 + 30, 42, 0]}>
        <boxGeometry args={[35, 30, 35]} />
        <meshStandardMaterial color={style.superstructure} roughness={0.6} metalness={0.3} />
      </mesh>
      <mesh position={[-shipLength/2 + 30, 50, 18.5]}>
        <boxGeometry args={[28, 8, 0.5]} />
        <meshStandardMaterial
          color={DESIGN_SYSTEM.equipment.glass}
          transparent
          opacity={0.6}
          roughness={0.2}
          metalness={0.4}
        />
      </mesh>
      <mesh position={[-shipLength/2 + 30, 68, 0]}>
        <cylinderGeometry args={[5, 6, 20, 12]} />
        <meshStandardMaterial color={style.funnel} roughness={0.55} />
      </mesh>
      <mesh position={[-shipLength/2 + 30, 79, 0]}>
        <cylinderGeometry args={[5.2, 5.2, 2, 12]} />
        <meshStandardMaterial color={DESIGN_SYSTEM.equipment.metal} roughness={0.6} />
      </mesh>
      {containers.map((container, i) => (
        <mesh key={i} position={[container.x, 32 + container.layer * 8.5, container.z]}>
          <boxGeometry args={[8, 8, 20]} />
          <meshStandardMaterial color={container.color} roughness={0.6} metalness={0.2} />
        </mesh>
      ))}
      <Html position={[0, 78, 30]} center distanceFactor={300}>
        <div style={{
          background: DESIGN_SYSTEM.label.bg,
          border: `1px solid ${DESIGN_SYSTEM.label.border}`,
          color: DESIGN_SYSTEM.label.text,
          padding: '3px 10px',
          borderRadius: '3px',
          fontSize: '10px',
          fontFamily: 'JetBrains Mono, monospace',
          fontWeight: '500',
          boxShadow: '0 1px 4px rgba(0,0,0,0.1)',
          whiteSpace: 'nowrap',
        }}>
          {id}
        </div>
      </Html>
    </group>
  )
}

export function PortStructures() {
  const { networkNodes } = useSimulationStore()

  const yardConfigs = useMemo(() => {
    const aRoadNodes = networkNodes.filter(n => n.id.startsWith('a'))
    if (aRoadNodes.length === 0) return getDefaultYardConfigs()

    const roadGroups: Record<string, typeof aRoadNodes> = {}
    aRoadNodes.forEach(node => {
      const parts = node.id.split('_')
      if (parts.length >= 2) {
        const roadId = `${parts[0]}_${parts[1]}`
        if (!roadGroups[roadId]) roadGroups[roadId] = []
        roadGroups[roadId].push(node)
      }
    })

    const roadInfos: Array<{ id: string; centerX: number; minZ: number; maxZ: number }> = []
    Object.entries(roadGroups).forEach(([roadId, nodes]) => {
      if (nodes.length === 0) return
      const xs = nodes.map(n => n.position.x)
      const zs = nodes.map(n => n.position.z)
      roadInfos.push({
        id: roadId,
        centerX: (Math.min(...xs) + Math.max(...xs)) / 2,
        minZ: Math.min(...zs),
        maxZ: Math.max(...zs),
      })
    })

    roadInfos.sort((a, b) => a.centerX - b.centerX)
    const configs = []
    const roadsPerYard = 4
    let yardIndex = 0

    for (let i = 0; i < roadInfos.length; i += roadsPerYard) {
      const groupRoads = roadInfos.slice(i, i + roadsPerYard)
      if (groupRoads.length < roadsPerYard) continue
      const minX = Math.min(...groupRoads.map(r => r.centerX))
      const maxX = Math.max(...groupRoads.map(r => r.centerX))
      const centerX = (minX + maxX) / 2
      const width = maxX - minX + 30
      const minZ = Math.min(...groupRoads.map(r => r.minZ))
      const maxZ = Math.max(...groupRoads.map(r => r.maxZ))
      const laneOffsets = groupRoads.map(r => r.centerX - centerX)

      configs.push({
        id: `YARD-${yardIndex}`,
        centerX,
        width,
        aRoadMinZ: minZ,
        aRoadMaxZ: maxZ,
        laneOffsets,
      })
      yardIndex++
    }
    return configs.length > 0 ? configs : getDefaultYardConfigs()
  }, [networkNodes])

  const apronBounds = useMemo(() => {
    if (yardConfigs.length === 0) return null

    const firstYard = yardConfigs[0]
    const lastYard = yardConfigs[yardConfigs.length - 1]

    const minLaneCenter = firstYard.centerX - firstYard.width / 2
    const maxLaneCenter = lastYard.centerX + lastYard.width / 2

    const ROAD_EDGE_PADDING = 15

    const globalMinX = minLaneCenter - ROAD_EDGE_PADDING
    const globalMaxX = maxLaneCenter + ROAD_EDGE_PADDING

    return {
      width: globalMaxX - globalMinX,
      centerX: (globalMinX + globalMaxX) / 2
    }
  }, [yardConfigs])

  const apronZ = useMemo(() => {

    const slNodes = networkNodes.filter(n => n.id.startsWith('sl'))

    if (slNodes.length === 0) return 530

    const maxSLNodeZ = Math.max(...slNodes.map(n => n.position.z))

    const slRoadEdgeZ = maxSLNodeZ + (ROAD_Z_STEP / 2)

    return slRoadEdgeZ + (APRON_DEPTH / 2)
  }, [networkNodes])

  const qcPositions = [
    { id: 'QC-0', x: 150 },
    { id: 'QC-1', x: 450 },
    { id: 'QC-2', x: 750 },
    { id: 'QC-3', x: 1050 },
  ]

  const shipConfigs = [
    { id: 'VESSEL-A', x: 300, z: apronZ + 150, seed: 1000 },
    { id: 'VESSEL-B', x: 900, z: apronZ + 150, seed: 2000 },
  ]

  const yardDepth = 120

  return (
    <group name="port-structures">
      {shipConfigs.map(ship => (
        <Ship
          key={ship.id}
          position={[ship.x, 0, ship.z]}
          id={ship.id}
          seed={ship.seed}
        />
      ))}

      {apronBounds && (
        <QCApron
          width={apronBounds.width}
          centerX={apronBounds.centerX}
          z={apronZ}
        />
      )}

      {qcPositions.map(qc => (
        <QCCrane
          key={qc.id}
          id={qc.id}
          position={[qc.x, 0, apronZ]}
        />
      ))}

      {yardConfigs.map((yard, idx) => {
        const yardZ = yard.aRoadMinZ - yardDepth / 2 - 10
        const trackCenterZ = (yard.aRoadMaxZ + yardZ) / 2
        return (
          <group key={yard.id}>
            <YardArea
              id={yard.id}
              position={[yard.centerX, 0, yardZ]}
              width={yard.width}
              depth={yardDepth}
              laneOffsets={yard.laneOffsets}
              seed={idx * 1000 + 3000}
            />
            <RTGCrane
              position={[yard.centerX, 0, trackCenterZ]}
              spanWidth={yard.width}
              id={`RTG-${idx}`}
            />
          </group>
        )
      })}
    </group>
  )
}

function getDefaultYardConfigs() {
  const configs = []
  const startX = 90
  const spacing = 120
  for (let i = 0; i < 10; i++) {
    configs.push({
      id: `YARD-${i}`,
      centerX: startX + i * spacing,
      width: 100,
      aRoadMinZ: -150,
      aRoadMaxZ: 50,
      laneOffsets: [-33, -11, 11, 33],
    })
  }
  return configs
}
