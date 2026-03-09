import { ref, onUnmounted } from 'vue'
import type { WSEvent } from '@/types'

export function useWebSocket(sessionId: string | number) {
  const connected = ref(false)
  const lastEvent = ref<WSEvent | null>(null)
  const handlers = new Map<string, Set<(data: Record<string, unknown>) => void>>()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function connect() {
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws/${sessionId}`
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onclose = () => {
      connected.value = false
      // Auto reconnect
      reconnectTimer = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      connected.value = false
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSEvent = JSON.parse(event.data)
        lastEvent.value = msg
        const eventHandlers = handlers.get(msg.event)
        if (eventHandlers) {
          eventHandlers.forEach(handler => handler(msg.data))
        }
        // Also notify wildcard listeners
        const wildcardHandlers = handlers.get('*')
        if (wildcardHandlers) {
          wildcardHandlers.forEach(handler => handler({ event: msg.event, ...msg.data }))
        }
      } catch {
        // ignore parse errors
      }
    }
  }

  function on(event: string, handler: (data: Record<string, unknown>) => void) {
    if (!handlers.has(event)) {
      handlers.set(event, new Set())
    }
    handlers.get(event)!.add(handler)
  }

  function off(event: string, handler: (data: Record<string, unknown>) => void) {
    handlers.get(event)?.delete(handler)
  }

  function send(event: string, data?: Record<string, unknown>) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ event, data }))
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
    }
    ws?.close()
    ws = null
    connected.value = false
  }

  connect()

  onUnmounted(() => {
    disconnect()
  })

  return { connected, lastEvent, on, off, send, disconnect }
}
