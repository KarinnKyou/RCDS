import { useEffect, useRef, useCallback } from 'react'
import { useSimulationStore } from '../stores/simulationStore'

const WS_URL = 'ws://127.0.0.1:8000'

let cachedNetworkNodes: unknown[] | null = null
let cachedNetworkEdges: unknown[] | null = null
let cachedJobPoints: Record<string, unknown> | null = null

export function useSimulationWebSocket() {
  const ws = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const isConnecting = useRef(false)

  const connectRef = useRef<() => void>(() => {})

  const {
    setConnected,
    setRunning,
    setTime,
    setMakespan,
    setFinished,
    setFleet,
    setMetrics,
    setApiStatus,
    setJobLocationStates,
    setNetworkData,
    setJobPoints,
    setStats,
    config,
  } = useSimulationStore()

  const connect = useCallback(() => {
    if (isConnecting.current) return
    if (ws.current && ws.current.readyState === WebSocket.OPEN) return

    if (ws.current) {
      ws.current.close()
      ws.current = null
    }

    isConnecting.current = true
    console.log('[ws] connecting', WS_URL)

    try {
      const socket = new WebSocket(WS_URL)
      ws.current = socket

      socket.onopen = () => {
        if (ws.current !== socket) return
        console.log('[ws] connected')
        isConnecting.current = false
        setConnected(true)

        if (cachedNetworkNodes && cachedNetworkEdges &&
            cachedNetworkNodes.length > 0) {
          setNetworkData(cachedNetworkNodes as never[], cachedNetworkEdges as never[])
        }
        if (cachedJobPoints) {
          setJobPoints(cachedJobPoints as never)
        }

        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current)
          reconnectTimer.current = null
        }
      }

      socket.onmessage = (event) => {
        if (ws.current !== socket) return
        try {
          const message = JSON.parse(event.data)
          const data = message.data

          switch (message.type) {
            case 'network':
              if (data?.nodes && data?.edges) {
                cachedNetworkNodes = data.nodes
                cachedNetworkEdges = data.edges
                setNetworkData(data.nodes, data.edges)
              }
              break

            case 'jobPoints':
              if (data) {
                cachedJobPoints = data
                setJobPoints(data)
              }
              break

            case 'state_update':
              setFleet({
                agvs: data.agvs || [],
                tasks: data.tasks || [],
                risks: data.risks || [],
                rescheduleLog: data.rescheduleLog || [],
              })
              setMetrics({
                kpis: data.kpis,
                agvEfficiency: data.agvEfficiency,
                statusDistribution: data.statusDistribution,
              })
              if (data.apiStatus) setApiStatus(data.apiStatus)
              if (data.jobLocationStates) {
                setJobLocationStates(data.jobLocationStates)
              }
                      if (data.stats) setStats(data.stats)
              if (data.time !== undefined) setTime(data.time)
              if (data.makespan !== undefined) setMakespan(data.makespan)
              if (data.isRunning !== undefined) setRunning(data.isRunning)
              if (data.finished !== undefined) setFinished(data.finished)
              break

            case 'finished':
              console.log('[ws] run finished', data)
              setRunning(false)
              setFinished(true)
              break

            case 'error':
              console.error('[ws] backend error:', data?.message)
              break
          }
        } catch (e) {
          console.error('[ws] parse error:', e)
        }
      }

      socket.onclose = (event) => {

        if (ws.current !== socket) return
        console.log('[ws] closed, code', event.code)
        isConnecting.current = false
        setConnected(false)
        ws.current = null

        if (!reconnectTimer.current) {
          reconnectTimer.current = setTimeout(() => {
            reconnectTimer.current = null
            connectRef.current()
          }, 3000)
        }
      }

      socket.onerror = () => {
        if (ws.current !== socket) return
        console.error('[ws] connection error')
        isConnecting.current = false
      }
    } catch (e) {
      console.error('[ws] failed to open socket:', e)
      isConnecting.current = false
    }
  }, [setConnected, setRunning, setTime, setMakespan, setFinished, setFleet,
      setMetrics, setApiStatus, setJobLocationStates,
      setNetworkData, setJobPoints, setStats])

  const send = useCallback((action: string, params?: Record<string, unknown>) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ action, params }))
    } else {
      console.warn('[ws] not connected')
    }
  }, [])

  const start = useCallback(() => send('start'), [send])
  const pause = useCallback(() => send('pause'), [send])
  const step = useCallback(() => send('step'), [send])

  const reset = useCallback(() => {
    send('reset', {
      numAgvs: config.numAgvs,
      numTasks: config.numTasks,
    })
  }, [send, config])

  const setSpeed = useCallback((speed: number) => send('setSpeed', { speed }), [send])

  const addRisk = useCallback(
    (riskType: string, opts?: { zone?: string; jobPointId?: string; agvId?: string; duration?: number; locationWp?: string }) =>
      send('addRisk', { riskType, ...opts }),
    [send],
  )

  const clearRisks = useCallback(() => send('clearRisks'), [send])

  const setApiSimulation = useCallback(
    (enabled: boolean) => send('setApiSimulation', { enabled }),
    [send],
  )

  const triggerRiskSequence = useCallback(() => send('triggerRiskSequence'), [send])

  useEffect(() => {
    connectRef.current = connect
  }, [connect])

  useEffect(() => {
    connect()
    return () => {
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current)
        reconnectTimer.current = null
      }

      const socket = ws.current
      ws.current = null
      isConnecting.current = false
      if (socket) socket.close()
    }
  }, [connect])

  return {
    send, start, pause, step, reset, setSpeed,
    addRisk, clearRisks, setApiSimulation, triggerRiskSequence,
  }
}
