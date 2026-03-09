import { ref } from 'vue'
import type { WSEvent } from '@/types'
import { getWebSocketUrl, markBackendOffline, markBackendOnline } from '@/composables/useBackend'

export function useWebSocket(sessionId: string | number) {
  const connected = ref(false)
  const lastEvent = ref<WSEvent | null>(null)
  const handlers = new Map<string, Set<(data: Record<string, unknown>) => void>>()
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let intentionalClose = false

  function connect() {
    intentionalClose = false
    const url = getWebSocketUrl(sessionId)
    console.log(`[ARTA:WS] Connecting to ${url}`)
    ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      markBackendOnline()
      console.log(`[ARTA:WS] Connected (session=${sessionId})`)
    }

    ws.onclose = (ev) => {
      connected.value = false
      console.log(`[ARTA:WS] Closed (code=${ev.code}, reason=${ev.reason}, intentional=${intentionalClose})`)
      if (!intentionalClose) {
        markBackendOffline(`WebSocket closed (${ev.code})`)
        console.log('[ARTA:WS] Will reconnect in 3s...')
        reconnectTimer = setTimeout(connect, 3000)
      }
    }

    ws.onerror = (ev) => {
      connected.value = false
      markBackendOffline('WebSocket connection failed.')
      console.error('[ARTA:WS] Error:', ev)
    }

    ws.onmessage = (event) => {
      try {
        const msg: WSEvent = JSON.parse(event.data)
        console.log(`[ARTA:WS] Event: ${msg.event}`, msg.data)
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
      } catch (err) {
        console.error('[ARTA:WS] Parse error:', err, event.data)
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
      return true
    }
    return false
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
