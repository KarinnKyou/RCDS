import { useMemo } from 'react'
import * as THREE from 'three'
import type { NetworkNode, NetworkEdge } from '../../stores/simulationStore'

const DESIGN_SYSTEM = {
  road: {

    fill: '#9098a0',

    edge: '#505860',
  },
}

const ROAD_CONFIG = {
  X_STEP: 60,
  Z_STEP: 20,
  HEIGHT: 0.5,
}

interface RoadNetworkProps {
  nodes: NetworkNode[]
  edges: NetworkEdge[]
}

function RoadSegment({
  position,
  size,
}: {
  position: [number, number, number]
  size: [number, number]
}) {
  const [width, depth] = size

  return (
    <group position={position}>

      <mesh position={[0, ROAD_CONFIG.HEIGHT / 2, 0]}>
        <boxGeometry args={[width, ROAD_CONFIG.HEIGHT, depth]} />
        <meshStandardMaterial
          color={DESIGN_SYSTEM.road.fill}
          roughness={0.85}
          metalness={0.05}
        />
      </mesh>

      <lineSegments position={[0, ROAD_CONFIG.HEIGHT + 0.1, 0]}>
        <edgesGeometry args={[new THREE.BoxGeometry(width, 0.01, depth)]} />
        <lineBasicMaterial color={DESIGN_SYSTEM.road.edge} />
      </lineSegments>
    </group>
  )
}

export function RoadNetwork({ nodes, edges }: RoadNetworkProps) {
  const roadSegments = useMemo(() => {
  
    if (!nodes.length) {
      return []
    }

    const roadGroups: Record<string, NetworkNode[]> = {}

    nodes.forEach(node => {
      const id = node.id
      let groupKey = 'other'

      if (id.startsWith('sl') || id.startsWith('ll')) {
        groupKey = id.split('_')[0]
      } else if (id.startsWith('b')) {
        groupKey = id.split('_')[0]
      } else if (id.startsWith('a')) {
        const parts = id.split('_')
        if (parts.length >= 2) {
          groupKey = `${parts[0]}_${parts[1]}`
        }
      }

      if (!roadGroups[groupKey]) {
        roadGroups[groupKey] = []
      }
      roadGroups[groupKey].push(node)
    })

    let aMinX = Infinity
    let aMaxX = -Infinity

    Object.entries(roadGroups).forEach(([groupId, groupNodes]) => {
      if (groupId.startsWith('a') && groupNodes.length > 0) {
        const xs = groupNodes.map(n => n.position.x)
        const minX = Math.min(...xs) - ROAD_CONFIG.X_STEP / 2
        const maxX = Math.max(...xs) + ROAD_CONFIG.X_STEP / 2
        aMinX = Math.min(aMinX, minX)
        aMaxX = Math.max(aMaxX, maxX)
      }
    })

    if (aMinX === Infinity) {
      aMinX = 0
      aMaxX = 1200
    }

    const segments: Array<{
      id: string
      position: [number, number, number]
      size: [number, number]
    }> = []

    const bRoads: Array<{ groupId: string; centerX: number }> = []

    Object.entries(roadGroups).forEach(([groupId, groupNodes]) => {
      if (groupId.startsWith('b') && groupNodes.length > 0) {
        const xs = groupNodes.map(n => n.position.x)
        const centerX = (Math.min(...xs) + Math.max(...xs)) / 2
        bRoads.push({ groupId, centerX })
      }
    })

    bRoads.sort((a, b) => a.centerX - b.centerX)

    const excludedBRoads = new Set<string>()
    if (bRoads.length >= 2) {
      excludedBRoads.add(bRoads[0].groupId)
      excludedBRoads.add(bRoads[bRoads.length - 1].groupId)
    }

    Object.entries(roadGroups).forEach(([groupId, groupNodes]) => {
      if (groupNodes.length === 0) return

      let roadType = 'other'
      if (groupId.startsWith('sl')) roadType = 'sl'
      else if (groupId.startsWith('ll')) roadType = 'll'
      else if (groupId.startsWith('b')) roadType = 'b'
      else if (groupId.startsWith('a')) roadType = 'a'

      if (roadType === 'b' && excludedBRoads.has(groupId)) {
        return
      }

      const xs = groupNodes.map(n => n.position.x)
      const zs = groupNodes.map(n => n.position.z)

      let minX = Math.min(...xs) - ROAD_CONFIG.X_STEP / 2
      let maxX = Math.max(...xs) + ROAD_CONFIG.X_STEP / 2
      const minZ = Math.min(...zs) - ROAD_CONFIG.Z_STEP / 2
      const maxZ = Math.max(...zs) + ROAD_CONFIG.Z_STEP / 2

      if (roadType === 'sl' || roadType === 'll') {
        minX = Math.max(minX, aMinX)
        maxX = Math.min(maxX, aMaxX)
      }

      const centerX = (minX + maxX) / 2
      const centerZ = (minZ + maxZ) / 2
      const width = maxX - minX
      const depth = maxZ - minZ

      if (width > 5 && depth > 5) {
        segments.push({
          id: groupId,
          position: [centerX, 0, centerZ],
          size: [width, depth],
        })
      }
    })

  
    return segments
  }, [nodes, edges])

  if (roadSegments.length === 0) {
    return null
  }

  return (
    <group name="road-network">
      {roadSegments.map((segment) => (
        <RoadSegment
          key={segment.id}
          position={segment.position}
          size={segment.size}
        />
      ))}
    </group>
  )
}
