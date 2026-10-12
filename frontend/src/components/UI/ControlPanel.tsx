import { useState } from 'react'
import { useSimulationStore } from '../../stores/simulationStore'
import type { CameraPreset } from '../../stores/simulationStore'

interface ControlPanelProps {
  isRunning: boolean
  onStart: () => void
  onPause: () => void
  onReset: () => void
  onStep: () => void
  onSpeedChange: (speed: number) => void
}

export function ControlPanel({
  isRunning,
  onStart,
  onPause,
  onReset,
  onStep,
  onSpeedChange,
}: ControlPanelProps) {
  const {
    config, setConfig, setCameraPreset, cameraPreset, time, finished,
    isConnected, viewMode,
  } = useSimulationStore()
  const [speed, setSpeed] = useState(1.0)

  const handleSpeedChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newSpeed = parseFloat(e.target.value)
    setSpeed(newSpeed)
    onSpeedChange(newSpeed)
  }

  const primary = (() => {
    if (!isConnected) {
      return { text: 'OFFLINE', onClick: () => {}, disabled: true, isPrimary: false }
    }
    if (isRunning) {
      return { text: 'PAUSE', onClick: onPause, disabled: false, isPrimary: false }
    }
    if (finished) {
      return { text: 'FINISHED', onClick: () => {}, disabled: true, isPrimary: false }
    }
    if (time > 0) {
      return { text: 'RESUME', onClick: onStart, disabled: false, isPrimary: true }
    }
    return { text: 'START', onClick: onStart, disabled: false, isPrimary: true }
  })()

  return (
    <aside className="control-panel">
      <div className="panel-header">
        <svg className="panel-header__icon" viewBox="0 0 24 24" fill="none"
             stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
        <span className="panel-header__title">Controls</span>
      </div>

      <div className="control-section">
        <div className="control-section__title">Simulation</div>
        <div className="control-buttons">
          <button
            className={`control-btn ${primary.isPrimary ? 'control-btn--primary' : ''}`}
            onClick={primary.onClick}
            disabled={primary.disabled}
            style={primary.disabled ? { opacity: 0.6 } : undefined}
          >
            {primary.text}
          </button>
          <button className="control-btn control-btn--danger" onClick={onReset}
                  disabled={!isConnected}>
            RESET
          </button>
          <button
            className="control-btn"
            onClick={onStep}
            disabled={!isConnected || isRunning}
            title="Advance a single tick (pause first to watch risk linkage frame by frame)"
          >
            STEP
          </button>
        </div>
      </div>

      <div className="control-section">
        <div className="speed-control">
          <div className="speed-control__header">
            <span className="speed-control__label">Playback Speed</span>
            <span className="speed-control__value">{speed.toFixed(1)}x</span>
          </div>
          <input
            type="range"
            className="speed-slider"
            min="0.5"
            max="5"
            step="0.5"
            value={speed}
            onChange={handleSpeedChange}
          />
        </div>
      </div>

      <div className="control-section">
        <div className="control-section__title">Configuration</div>
        <div className="config-form">
          <div className="config-field">
            <label className="config-field__label">AGV Count</label>
            <input
              type="number"
              className="config-field__input"
              value={config.numAgvs}
              min={1}
              max={24}
              onChange={(e) =>
                setConfig({ numAgvs: parseInt(e.target.value) || 5 })}
            />
          </div>
          <div className="config-field">
            <label className="config-field__label">Total Tasks</label>
            <input
              type="number"
              className="config-field__input"
              value={config.numTasks}
              min={0}
              max={400}
              onChange={(e) =>
                setConfig({ numTasks: parseInt(e.target.value) || 0 })}
            />
          </div>
        </div>
      </div>

      <div className="control-section">
        <div className="control-section__title">Camera Presets</div>
        <div className="control-buttons">
          {(['top', 'front', 'side', 'iso'] as Exclude<CameraPreset, null>[]).map((p) => (
            <button
              key={p}
              className={`control-btn ${cameraPreset === p && viewMode === '3d' ? 'control-btn--active' : ''}`}
              style={{ flex: '1 1 0', minWidth: 0, padding: '0 4px', fontSize: '10px' }}
              disabled={viewMode === '2d'}
              onClick={() => setCameraPreset(p)}
            >
              {p.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </aside>
  )
}
