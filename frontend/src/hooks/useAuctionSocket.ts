import { useEffect, useRef, useState } from 'react'

import { API_BASE_URL } from '@/api/client'

export type SocketStatus = 'connecting' | 'open' | 'reconnecting' | 'closed'

/** Server -> client messages on /ws/auctions/{id}. */
export type AuctionMessage = { type: string; auction_id?: number; [key: string]: unknown }

function socketUrl(auctionId: string): string {
  // Same origin by default (the Vite dev server proxies /ws to the backend).
  const base = API_BASE_URL ? new URL(API_BASE_URL) : window.location
  const proto = base.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${base.host}/ws/auctions/${auctionId}`
}

const PING_MS = 25_000
const MAX_BACKOFF_MS = 10_000

/**
 * Subscribe to live auction events. Reconnects with exponential backoff and
 * keeps the connection warm with PINGs. `onMessage` may change between
 * renders without reconnecting.
 */
export function useAuctionSocket(auctionId: string, onMessage: (msg: AuctionMessage) => void): SocketStatus {
  const [status, setStatus] = useState<SocketStatus>('connecting')
  const handler = useRef(onMessage)
  handler.current = onMessage

  useEffect(() => {
    let ws: WebSocket | null = null
    let retry = 0
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    let pingTimer: ReturnType<typeof setInterval> | undefined
    let disposed = false

    const connect = () => {
      setStatus(retry === 0 ? 'connecting' : 'reconnecting')
      ws = new WebSocket(socketUrl(auctionId))

      ws.onopen = () => {
        retry = 0
        setStatus('open')
        pingTimer = setInterval(() => ws?.readyState === WebSocket.OPEN && ws.send('{"type":"PING"}'), PING_MS)
      }
      ws.onmessage = (e) => {
        try {
          handler.current(JSON.parse(e.data) as AuctionMessage)
        } catch {
          /* ignore malformed frames */
        }
      }
      ws.onclose = (e) => {
        clearInterval(pingTimer)
        if (disposed) return
        if (e.code === 1008) {
          setStatus('closed') // auction not found; don't retry
          return
        }
        retry += 1
        setStatus('reconnecting')
        retryTimer = setTimeout(connect, Math.min(MAX_BACKOFF_MS, 500 * 2 ** retry))
      }
    }

    connect()
    return () => {
      disposed = true
      clearTimeout(retryTimer)
      clearInterval(pingTimer)
      ws?.close()
    }
  }, [auctionId])

  return status
}
