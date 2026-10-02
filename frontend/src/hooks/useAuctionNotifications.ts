import { useCallback } from 'react'

import type { User } from '@/types'
import { formatINR } from '@/utils/format'

import type { AuctionMessage } from './useAuctionSocket'
import { useToast } from './useToast'

/** Personal toasts derived from an auction's broadcast events. */
export function useAuctionNotifications(user: User | null) {
  const { notify } = useToast()
  return useCallback(
    (msg: AuctionMessage) => {
      if (!user) return
      if (msg.type === 'OUTBID' && msg.outbid_user_id === user.id) {
        notify({
          tone: 'warning',
          title: 'You lost your seat',
          body: `A higher bid of ${formatINR(Number(msg.amount))} took it. Bid at least ${formatINR(Number(msg.next_min_bid))} to get a seat back.`,
        })
      } else if (msg.type === 'QUALIFYING_CLOSED' && (msg.confirmed_ids as number[]).includes(user.id)) {
        notify({ tone: 'success', title: 'Your seat is confirmed', body: 'You finished in the top 2 of the qualifying round.' }, 8000)
      } else if (msg.type === 'AUCTION_COMPLETED') {
        const mine = (msg.winners as { advertiser_id: number; seat: number; amount: number }[]).find(
          (w) => w.advertiser_id === user.id,
        )
        if (mine) notify({ tone: 'success', title: `You won seat ${mine.seat}`, body: `At ${formatINR(mine.amount)}.` }, 8000)
      }
    },
    [user, notify],
  )
}
