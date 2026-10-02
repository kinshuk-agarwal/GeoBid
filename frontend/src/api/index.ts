import type { Auction, Bid, FootfallProfile, MapResponse, Pole, PoleInventory, PriceTrend, PublicConfig, TokenResponse, User } from '@/types'

import { api } from './client'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }).then((r) => r.data),
  me: () => api.get<User>('/auth/me').then((r) => r.data),
}

export const configApi = {
  get: () => api.get<PublicConfig>('/config').then((r) => r.data),
}

export interface MapQuery {
  latitude: number
  longitude: number
  radius_km: number
  top_limit?: number
}

export const mapApi = {
  poles: (q: MapQuery, signal?: AbortSignal) =>
    api.get<MapResponse>('/map/poles', { params: q, signal }).then((r) => r.data),
}

export const polesApi = {
  list: () => api.get<Pole[]>('/poles').then((r) => r.data),
  get: (idOrCode: string | number) => api.get<Pole>(`/poles/${idOrCode}`).then((r) => r.data),
  /** The pole's shifts for `date` (YYYY-MM-DD); defaults to tomorrow. */
  inventory: (idOrCode: string | number, date?: string, signal?: AbortSignal) =>
    api
      .get<PoleInventory>(`/poles/${idOrCode}/inventory`, { params: date ? { date } : {}, signal })
      .then((r) => r.data),
  footfallProfile: (idOrCode: string | number, date?: string, signal?: AbortSignal) =>
    api
      .get<FootfallProfile>(`/poles/${idOrCode}/footfall-profile`, { params: date ? { date } : {}, signal })
      .then((r) => r.data),
  priceTrend: (idOrCode: string | number, shift: string, date?: string, signal?: AbortSignal) =>
    api
      .get<PriceTrend>(`/poles/${idOrCode}/price-trend`, { params: { shift, ...(date ? { date } : {}) }, signal })
      .then((r) => r.data),
}

export const auctionsApi = {
  get: (id: number | string, signal?: AbortSignal) =>
    api.get<Auction>(`/auctions/${id}`, { signal }).then((r) => r.data),
  bids: (id: number | string, signal?: AbortSignal) =>
    api.get<Bid[]>(`/auctions/${id}/bids`, { signal }).then((r) => r.data),
  placeBid: (id: number | string, amount: number) =>
    api.post<{ bid: Bid; auction: Auction }>(`/auctions/${id}/bids`, { amount }).then((r) => r.data),
}
