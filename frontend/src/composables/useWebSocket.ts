import { ref } from 'vue'
import type { WSEvent } from '@/types'

export function useWebSocket(sessionId: string | number) {
  const connected = ref(false)
  const lastEvent = ref<WSEvent | null>(null)
  const handlers = new Map<string, Set<(data: Record<string, unknown>) => void>>()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let intentionalClose = false

  function connect() {
    intentionalClose = false
    const isTauri = !!(window as Record<string, unknown>).__TAURI_INTERNALS__
    const url = isTauri
      ? `ws://127.0.0.1:8721/ws/${sessionId}`
      : `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws/${sessionId}`
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
    }

    ws.onclose = () => {
      connected.value = false
      if (!intentionalClose) {
        reconnectTimer = setTimeout(connect, 3000)
      }
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
    intentionalClose = true
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    ws?.close()
    ws = null
    connected.value = false
  }

  connect()

  return { connected, lastEvent, on, off, send, disconnect }
}
