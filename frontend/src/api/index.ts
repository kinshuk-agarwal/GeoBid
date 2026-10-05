import type {
  AdvertiserDashboardData,
  AuctionRow,
  BidHistoryPage,
  FinanceDashboardData,
  FinanceGranularity,
  PoleAnalysisData,
  TariffConfig,
  Video,
} from '@/types'
import type { Auction, Bid, FootfallProfile, MapResponse, Pole, PoleInventory, PriceTrend, PublicConfig, TokenResponse, User } from '@/types'

import { api } from './client'

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>('/auth/login', { email, password }).then((r) => r.data),
  me: () => api.get<User>('/auth/me').then((r) => r.data),
}

export const configApi = {
  get: () => api.get<PublicConfig>('/config').then((r) => r.data),
  tariff: () => api.get<TariffConfig>('/tariff/config').then((r) => r.data),
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

export interface OpportunityQuery {
  date?: string
  shift?: string
  category?: string
  min_footfall?: number
  min_score?: number
  max_price?: number
  round?: string
  latitude?: number
  longitude?: number
  radius_km?: number
  limit?: number
}

export const dashboardApi = {
  poleAnalysis: (code: string) => api.get<PoleAnalysisData>(`/dashboard/poles/${code}/analysis`).then((r) => r.data),
  advertiser: () => api.get<AdvertiserDashboardData>('/dashboard/advertiser').then((r) => r.data),
  /** ``days`` = window for charts and rankings; 0 = all time. */
  finance: (days: number, granularity: FinanceGranularity) =>
    api.get<FinanceDashboardData>('/dashboard/admin/finance', { params: { days, granularity } }).then((r) => r.data),
  myBids: (limit = 25, offset = 0) =>
    api.get<BidHistoryPage>('/dashboard/advertiser/bids', { params: { limit, offset } }).then((r) => r.data),
  opportunities: (q: OpportunityQuery) => api.get<AuctionRow[]>('/dashboard/opportunities', { params: q }).then((r) => r.data),
}

/** Auctioneer actions (admin only). */
export const adminApi = {
  createAuction: (body: { inventory_slot_id: number }) => api.post<Auction>('/auctions', body).then((r) => r.data),
  start: (id: number) => api.post<Auction>(`/auctions/${id}/start`).then((r) => r.data),
  advance: (id: number) => api.post<Auction>(`/auctions/${id}/advance`).then((r) => r.data),
  complete: (id: number) => api.post<Auction>(`/auctions/${id}/complete`).then((r) => r.data),
}

export const videosApi = {
  list: () => api.get<Video[]>('/videos').then((r) => r.data),
}
