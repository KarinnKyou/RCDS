import { Suspense, useRef, useEffect } from 'react'
import type { ComponentRef } from 'react'
import { Canvas, useThree } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import { useSimulationStore, CAMERA_PRESETS } from '../../stores/simulationStore'
import { AGVFleet } from './AGV'
import { RoadNetwork } from './RoadNetwork'
import { PortStructures } from './PortStructures'
import { RiskLayer } from './RiskLayer'
import * as THREE from 'three'

const SCENE_COLOR = '#c8cdd3'

const SCENE_MIRROR_Z: [number, number, number] = [1, 1, -1]

const DESIGN_SYSTEM = {
  background: SCENE_COLOR,
  fog: {
    color: SCENE_COLOR,
    near: 1200,
    far: 3500,
  },
}

function LoadingFallback() {
  return (
    <group>
      <mesh position={[600, 30, 250]}>
        <boxGeometry args={[30, 30, 30]} />
        <meshBasicMaterial color="#9aa3b0" wireframe />
      </mesh>
    </group>
  )
}

function Lighting() {
  return (
    <>
      <ambientLight intensity={0.6} color="#ffffff" />
      <directionalLight
        position={[400, 800, 400]}
        intensity={1.5}
        color="#fffaf5"
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-camera-far={2000}
        shadow-camera-left={-800}
        shadow-camera-right={800}
        shadow-camera-top={800}
        shadow-camera-bottom={-800}
        shadow-bias={-0.0001}
      />
      <directionalLight position={[-300, 400, -200]} intensity={0.5} color="#f5f8ff" />
      <hemisphereLight color="#a0d0e8" groundColor={SCENE_COLOR} intensity={0.4} />
    </>
  )
}

function Ground() {
  return (
    <group>

      <mesh
        rotation={[-Math.PI / 2, 0, 0]}
        position={[600, -0.1, 150]}
        receiveShadow
      >
        <planeGeometry args={[5000, 5000]} />
        <shadowMaterial transparent opacity={0.2} color="#000000" />
      </mesh>

      <Grid
        position={[0, -0.05, 0]}
        args={[3000, 3000]}
        cellSize={60}
        sectionSize={240}
        fadeDistance={1800}
        fadeStrength={1.5}
        cellColor="#b0b8c4"
        sectionColor="#8a95a3"
        infiniteGrid
      />
    </group>
  )
}

function CameraController() {
  const { camera } = useThree()

  const controlsRef = useRef<ComponentRef<typeof OrbitControls>>(null)
  const { cameraPreset, cameraUpdateTrigger } = useSimulationStore()

  const animationRef = useRef<{
    startPosition: THREE.Vector3
    endPosition: THREE.Vector3
    startTarget: THREE.Vector3
    endTarget: THREE.Vector3
    progress: number
    isAnimating: boolean
  }>({
    startPosition: new THREE.Vector3(),
    endPosition: new THREE.Vector3(),
    startTarget: new THREE.Vector3(),
    endTarget: new THREE.Vector3(),
    progress: 0,
    isAnimating: false,
  })

  useEffect(() => {

    if (cameraUpdateTrigger === 0 || cameraPreset === null) return

    const preset = CAMERA_PRESETS[cameraPreset]
    if (!preset) return

    const anim = animationRef.current

    anim.startPosition.copy(camera.position)
    anim.endPosition.set(...preset.position)

    if (controlsRef.current) {
      anim.startTarget.copy(controlsRef.current.target)
    }
    anim.endTarget.set(...preset.target)

    anim.progress = 0
    anim.isAnimating = true

    const animate = () => {
      if (!anim.isAnimating) return

      anim.progress += 0.03

      if (anim.progress >= 1) {
        anim.progress = 1
        anim.isAnimating = false
      }

      const t = anim.progress < 0.5
        ? 4 * anim.progress * anim.progress * anim.progress
        : 1 - Math.pow(-2 * anim.progress + 2, 3) / 2

      camera.position.lerpVectors(anim.startPosition, anim.endPosition, t)

      if (controlsRef.current) {
        controlsRef.current.target.lerpVectors(anim.startTarget, anim.endTarget, t)
        controlsRef.current.update()
      }

      if (anim.isAnimating) {
        requestAnimationFrame(animate)
      }
    }

    requestAnimationFrame(animate)
  }, [cameraPreset, cameraUpdateTrigger, camera])

  return (
    <OrbitControls
      ref={controlsRef}
      enablePan
      enableZoom
      enableRotate
      target={[600, 0, -250]}
      maxPolarAngle={Math.PI / 2.05}
      minPolarAngle={0.1}
      minDistance={80}
      maxDistance={1800}
      panSpeed={0.8}
      rotateSpeed={0.5}
      zoomSpeed={1.0}
      enableDamping
      dampingFactor={0.05}
    />
  )
}

export function PortScene() {
  const { networkNodes, networkEdges, agvStates, selectedAgvId } = useSimulationStore()

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      <Canvas
        camera={{

          position: [600, 520, 780],
          fov: 50,
          near: 1,
          far: 5000
        }}
        style={{ background: DESIGN_SYSTEM.background }}
        shadows
        dpr={[1, 2]}
        gl={{
          antialias: true,
          alpha: false,
          powerPreference: 'high-performance',
          toneMapping: 1,
          toneMappingExposure: 1.0,
        }}
      >
        <Suspense fallback={<LoadingFallback />}>
          <color attach="background" args={[DESIGN_SYSTEM.background]} />

          <Lighting />

          <fog attach="fog" args={[
            DESIGN_SYSTEM.fog.color,
            DESIGN_SYSTEM.fog.near,
            DESIGN_SYSTEM.fog.far
          ]} />

          <Ground />

          <group name="port-world" scale={SCENE_MIRROR_Z}>
            <RoadNetwork nodes={networkNodes} edges={networkEdges} />
            <PortStructures />
            <AGVFleet agvs={agvStates} selectedId={selectedAgvId} />

            <RiskLayer />
          </group>

          <CameraController />
        </Suspense>
      </Canvas>
    </div>
  )
}
