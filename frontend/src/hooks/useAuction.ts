import { useCallback, useEffect, useRef, useState } from 'react'

import { auctionsApi } from '@/api'
import { errorMessage } from '@/api/client'
import type { Auction, Bid } from '@/types'

import { useAuctionSocket, type AuctionMessage, type SocketStatus } from './useAuctionSocket'

/** Fallback refresh interval, used only while the WebSocket is down. */
const FALLBACK_POLL_MS = 5000

interface NewBidMessage {
  bid_id: number
  amount: number
  bidder_id: number
  bidder_alias: string
  round: 'QUALIFYING' | 'PREMIUM'
  timestamp: string
}

/**
 * Live auction state. Loads over REST, then stays current via the auction's
 * WebSocket (SNAPSHOT / NEW_BID / AUCTION_* events). Polls only while the
 * socket is disconnected.
 */
export function useAuction(id: string, onEvent?: (msg: AuctionMessage) => void) {
  const [auction, setAuction] = useState<Auction | null>(null)
  const [bids, setBids] = useState<Bid[]>([])
  const [error, setError] = useState<string | null>(null)
  /** server clock minus browser clock, in ms */
  const [clockOffset, setClockOffset] = useState(0)
  const [viewers, setViewers] = useState<number | null>(null)
  /** id of the most recent bid received live, for highlight animations */
  const [lastLiveBidId, setLastLiveBidId] = useState<number | null>(null)
  const alive = useRef(true)

  const refresh = useCallback(async () => {
    try {
      const sent = Date.now()
      const [a, b] = await Promise.all([auctionsApi.get(id), auctionsApi.bids(id)])
      if (!alive.current) return
      const rtt = Date.now() - sent
      setClockOffset(new Date(a.server_time).getTime() - (sent + rtt / 2))
      setAuction(a)
      setBids(b)
      setError(null)
    } catch (e) {
      if (alive.current) setError(errorMessage(e, 'Could not load auction'))
    }
  }, [id])

  useEffect(() => {
    alive.current = true
    setAuction(null)
    setBids([])
    setViewers(null)
    void refresh()
    return () => {
      alive.current = false
    }
  }, [refresh])

  const handleMessage = useCallback(
    (msg: AuctionMessage) => {
      switch (msg.type) {
        case 'SNAPSHOT':
          setBids(msg.bids as Bid[])
          void refresh() // REST adds the signed-in viewer's own seat and minimum
          break
        case 'NEW_BID': {
          const m = msg as unknown as NewBidMessage
          setBids((prev) =>
            prev.some((b) => b.id === m.bid_id)
              ? prev
              : [
                  {
                    id: m.bid_id,
                    auction_id: Number(id),
                    advertiser_id: m.bidder_id,
                    bidder_alias: m.bidder_alias,
                    amount: m.amount,
                    round: m.round,
                    timestamp: m.timestamp,
                  },
                  ...prev,
                ].sort((x, y) => y.amount - x.amount),
          )
          setLastLiveBidId(m.bid_id)
          void refresh() // seats and your personal minimum changed
          break
        }
        case 'AUCTION_STARTED':
        case 'QUALIFYING_CLOSED':
        case 'PREMIUM_ROUND_STARTED':
        case 'AUCTION_COMPLETED':
          void refresh() // pick up round, seats, winners from the source of truth
          break
        case 'VIEWERS':
          setViewers(Number(msg.count))
          break
      }
      onEvent?.(msg)
    },
    [id, refresh, onEvent],
  )

  const socket: SocketStatus = useAuctionSocket(id, handleMessage)

  // Fallback: poll while the socket is down and the auction is still open.
  const open = auction?.status === 'LIVE' || auction?.status === 'SCHEDULED'
  useEffect(() => {
    if (!open || socket === 'open') return
    const t = setInterval(() => void refresh(), FALLBACK_POLL_MS)
    return () => clearInterval(t)
  }, [open, socket, refresh])

  /** Apply the auction returned by a successful bid without waiting for the push. */
  const applyBidResult = useCallback((a: Auction, bid: Bid) => {
    setAuction(a)
    setBids((prev) => (prev.some((b) => b.id === bid.id) ? prev : [bid, ...prev].sort((x, y) => y.amount - x.amount)))
  }, [])

  return { auction, bids, error, clockOffset, refresh, applyBidResult, socket, viewers, lastLiveBidId }
}
