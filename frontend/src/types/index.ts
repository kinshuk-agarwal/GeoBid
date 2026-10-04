export type Role = 'ADVERTISER' | 'ADMIN'
export type FootfallCategory = 'HIGH' | 'MEDIUM' | 'LOW'
export type PoleStatus = 'ACTIVE' | 'INACTIVE'

export interface User {
  id: number
  name: string
  email: string
  role: Role
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}

export interface LatLng {
  latitude: number
  longitude: number
}

export interface Road {
  id: number
  name: string
  latitude: number
  longitude: number
  importance_score: number
  path: [number, number][]
  pole_count: number
}

export interface Pole {
  id: number
  code: string
  name: string
  road_id: number | null
  road_name: string | null
  latitude: number
  longitude: number
  footfall: number
  footfall_score: number
  visibility_score: number
  footfall_source: string
  footfall_updated_at: string | null
  category: FootfallCategory
  status: PoleStatus
  rank: number | null
  category_rank: number | null
  percentile: number | null
  distance_km: number | null
}

export interface MapResponse {
  center: LatLng
  radius_km: number
  roads: Road[]
  poles: Pole[]
  top: Record<FootfallCategory, Pole[]>
  counts: Record<FootfallCategory | 'total', number>
  notice: { footfall: string; geography: string }
}

export interface PublicConfig {
  default_location: LatLng & { name: string }
  default_radius_km: number
  allowed_radii_km: number[]
  footfall_data_notice: string
}

export type SlotStatus = 'AVAILABLE' | 'IN_AUCTION' | 'SOLD' | 'UNSOLD'
export type Demand = 'LOW' | 'LOW_MEDIUM' | 'MEDIUM' | 'HIGH' | 'VERY_HIGH'
export type MarketStatus = 'AVAILABLE' | 'AUCTIONING' | 'SOLD_OUT' | 'NO_INVENTORY'

/** Typical winning price for this pole-shift on this weekday (last 60 days). */
export interface ExpectedPrice {
  weekday: string
  average: number
  low: number
  high: number
  min_price: number
  max_price: number
  samples: number
  days: number
}

export interface TariffBreakdown {
  base_rate: number
  pole_value: number
  pole_multiplier: number
  shift_multiplier: number
  demand: Demand
  base_tariff: number
  reserve_price: number
  /** 'slot_footfall': priced by this slot's footfall; 'demand_table': configured fallback */
  basis: 'slot_footfall' | 'demand_table'
  slot_footfall: number | null
  avg_slot_footfall: number | null
}

export interface Slot {
  id: number
  pole_id: number
  pole_code: string
  pole_name: string
  pole_category: FootfallCategory
  footfall: number
  date: string
  shift: string
  shift_label: string
  demand: Demand
  start_time: string
  end_time: string
  base_tariff: number
  reserve_price: number
  status: SlotStatus
  tariff: TariffBreakdown
  auction: AuctionBrief | null
  expected_price: ExpectedPrice | null
  /** footfall during this slot on this date's weekday */
  slot_footfall: number | null
}

export interface PoleInventory {
  pole_id: number
  pole_code: string
  date: string
  is_tomorrow: boolean
  market_status: MarketStatus
  slots: Slot[]
}

export type AuctionStatus = 'SCHEDULED' | 'LIVE' | 'COMPLETED' | 'CANCELLED'
/** QUALIFYING: anyone bids, top 4 hold seats · BREAK: seats 1-2 confirmed, no bidding · PREMIUM: anyone bids for seats 3-4 */
export type AuctionRound = 'QUALIFYING' | 'BREAK' | 'PREMIUM' | 'CLOSED'
/** LEADING: top 2 in the qualifying round · CONFIRMED: secured at 12:00 · PROVISIONAL / PREMIUM: can be bumped · OPEN: empty · WON */
export type SeatStatus = 'LEADING' | 'CONFIRMED' | 'PROVISIONAL' | 'PREMIUM' | 'OPEN' | 'WON'

export interface AdSeat {
  seat: number
  advertiser_id: number | null
  alias: string | null
  amount: number | null
  status: SeatStatus
}

export interface AuctionBrief {
  id: number
  status: AuctionStatus
  round: AuctionRound | null
  round_ends_at: string | null
  end_time: string
  current_highest_bid: number | null
  bid_count: number
  /** what a newcomer must bid now; null when bidding is closed */
  next_min_bid: number | null
  premium_floor: number | null
  seats: AdSeat[]
}

export interface Winner {
  seat: number
  advertiser_id: number
  alias: string
  amount: number
}

/** The signed-in user's position (only present when signed in). */
export interface Viewer {
  seat: number | null
  seat_status: SeatStatus | null
  next_min_bid: number | null
  can_bid: boolean
  reason: string | null
}

export interface Auction {
  id: number
  status: AuctionStatus
  /** round implied by the server clock; null = not started */
  round: AuctionRound | null
  round_ends_at: string | null
  pole: {
    id: number
    code: string
    name: string
    road_name: string | null
    latitude: number
    longitude: number
    footfall: number
    footfall_score: number
    visibility_score: number
    category: FootfallCategory
  }
  inventory_slot_id: number
  slot_status: SlotStatus
  date: string
  shift: string
  shift_label: string
  demand: Demand
  shift_start: string
  shift_end: string
  start_time: string
  qualifying_end_time: string
  premium_start_time: string
  end_time: string
  seats: AdSeat[]
  seats_total: number
  confirmed_seats: number
  /** premium starting price: 1.5x the top qualifying bid (null before 12:00) */
  premium_floor: number | null
  reserve_price: number
  min_increment: number
  current_highest_bid: number | null
  next_min_bid: number | null
  bid_count: number
  completed_at: string | null
  winners: Winner[]
  revenue: number
  viewer: Viewer | null
  expected_price: ExpectedPrice | null
  slot_footfall: number | null
  server_time: string
}

export interface Bid {
  id: number
  auction_id: number
  advertiser_id: number
  bidder_alias: string
  amount: number
  round: 'QUALIFYING' | 'PREMIUM'
  timestamp: string
}

export interface PriceTrend {
  pole_code: string
  shift: string
  shift_label: string
  demand: Demand
  window_days: number
  points: { date: string; weekday: string; clearing_price: number | null; base_price: number; source: string }[]
  by_weekday: { weekday: string; average: number | null; low: number | null; high: number | null; samples: number; days: number }[]
  target_date: string
  expected: ExpectedPrice | null
  overall_average: number | null
  sell_through: number
  synthetic_share: number
}

export interface FootfallProfile {
  pole_code: string
  date: string
  weekday: string
  daily_total: number
  peak_shift: string | null
  slots: { shift: string; label: string; demand: Demand; footfall: number; share: number }[]
  by_weekday: { weekday: string; total: number }[]
  source: string
}

// --- dashboards ---

export interface AuctionRow {
  id: number
  pole_code: string
  pole_name: string
  category: FootfallCategory
  date: string
  shift: string
  shift_label: string
  status: AuctionStatus
  round: AuctionRound | null
  round_ends_at: string | null
  base_price: number
  top_bid: number | null
  next_min_bid: number | null
  seats_filled: number
  seats_total: number
  bid_count: number
  slot_footfall: number | null
  revenue: number
  my_bid?: number | null
  my_seat?: number | null
  my_seat_status?: SeatStatus | null
  my_min_bid?: number | null
}

export interface RevenuePoint {
  date: string
  revenue: number
  seats: number
}

export interface PoleAnalysisData {
  code: string
  name: string
  road_name: string | null
  category: FootfallCategory
  status: PoleStatus
  footfall: number
  footfall_score: number
  visibility_score: number
  open_slots: number
  window_days: number
  kpis: {
    revenue_total: number
    revenue_30d: number
    seats_sold: number
    avg_seat_price: number | null
    sell_through: number
    price_vs_base: number | null
  }
  revenue_by_day: RevenuePoint[]
  slots: { shift: string; label: string; avg_footfall: number; base_price: number; avg_price: number | null; sell_through: number }[]
}

export interface AdvertiserDashboardData {
  kpis: { seats_held: number; seats_at_risk: number; seats_won: number; total_spend: number; open_auctions: number }
  my_auctions: AuctionRow[]
  my_auctions_total: number
  won: { auction_id: number; pole_code: string; date: string; shift_label: string; seat: number; amount: number }[]
}

export interface UserBrief {
  id: number
  name: string
  email: string
  role: Role
}

/** GET /tariff/config: the pricing formula's inputs and the auction rules. */
export interface TariffConfig {
  base_rate: number
  footfall_weight: number
  visibility_weight: number
  pole_multiplier_min: number
  pole_multiplier_max: number
  rounding: number
  slot_footfall_exponent: number
  slot_multiplier_min: number
  slot_multiplier_max: number
  auction: {
    seats_per_slot: number
    confirmed_seats: number
    min_increment: number
    premium_floor_multiplier: number
    qualifying_close_time: string
    premium_round_start_time: string
    premium_close_before_slot_minutes: number
  }
}

export type BidOutcome = 'WON' | 'HOLDING' | 'OUTBID' | 'RAISED' | 'LOST' | 'CANCELLED'

export interface BidHistoryRow {
  bid_id: number
  placed_at: string
  auction_id: number
  pole_code: string
  category: FootfallCategory
  date: string
  shift_label: string
  amount: number
  round: 'QUALIFYING' | 'PREMIUM'
  outcome: BidOutcome
  seat: number | null
}

export interface BidHistoryPage {
  items: BidHistoryRow[]
  total: number
}
