# GeoBid

Real-time geospatial digital advertising auction POC. Advertisers discover
digital advertising poles around Kondapur, Hyderabad, ranked by footfall, and
bid for daily advertising shifts in live auctions.

> **All footfall values are synthetic.** They simulate the output of an
> upstream footfall model; GeoBid consumes them and does not compute footfall.

_Status: Phase 8 (dashboards) + 4-seat rolling-ad auctions (qualifying → break → premium), footfall-priced 2-hour slots, 7-day bidding window, price trends. This README will be expanded as the
remaining phases land._

## Backend quick start

Requires Python 3.11+.

**Windows (PowerShell)**

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m scripts.seed_database --reset
uvicorn app.main:app --reload --port 8000
```

**Linux / macOS**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed_database --reset
uvicorn app.main:app --reload --port 8000
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- Health: http://localhost:8000/api/health

Run tests from `backend/`: `python -m pytest`

## Frontend quick start

Requires Node.js 20.19+ or 22.12+. Start the backend first.

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api` and `/ws` to
the backend on port 8000 (override with `VITE_BACKEND_URL`), so no CORS setup
is needed in development.

Map tiles come from OpenStreetMap through the backend's **caching tile
proxy** (`/tiles/{z}/{x}/{y}.png`): each tile is fetched from OSM once, with an
identifying User-Agent as OSM's tile usage policy requires, and cached in
`backend/data/tile_cache/`. Browsers never call OSM directly, so the map also
works when the app is opened from another device (e.g. via port forwarding).
Set `GEOBID_TILE_UPSTREAM_URL` to use another tile server, or
`VITE_MAP_TILE_URL` / `VITE_MAP_TILE_ATTRIBUTION` to bypass the proxy.

## Synthetic data

`seed_database` generates the dataset automatically if it is missing. To
regenerate it explicitly (deterministic per seed):

```bash
python -m scripts.generate_synthetic_data --seed 42
python -m scripts.seed_database --reset
```

Files are written to `backend/data/generated/`:

| File | Represents |
|------|------------|
| `roads.json` | Major roads around Kondapur (approximate alignments) |
| `poles.csv` | Fictional pole sites along those roads |
| `footfall_model_output.csv` | Output of a simulated **upstream footfall model** |

GeoBid reads footfall only through `FootfallProvider`
(`app/footfall/`). `SyntheticFootfallProvider` reads the model-output file;
a real model can be added as another provider without touching ranking,
tariff or auction code.

Footfall categories are **relative**: the top 25% of poles by footfall are
HIGH, the next 40% MEDIUM, the rest LOW (`GEOBID_FOOTFALL_HIGH_SHARE`,
`GEOBID_FOOTFALL_MEDIUM_SHARE`).

## API so far

| Method | Path | Auth |
|--------|------|------|
| GET | `/api/map/poles?latitude=&longitude=&radius_km=` | public |
| GET | `/api/map/poles/nearby?latitude=&longitude=&radius_km=&limit=` | public |
| GET | `/api/poles` (filters: `category`, `min_footfall`, `min_score`, `road_id`) | public |
| GET | `/api/poles/{id or code}` | public |
| POST/PUT/DELETE | `/api/poles[/{id or code}]` | admin |
| GET | `/api/roads` | public |
| GET | `/api/footfall/source` | public |
| POST | `/api/footfall/refresh` | admin |
| GET | `/api/poles/{id or code}/inventory?date=` (default: tomorrow) | public |
| GET | `/api/inventory` (filters: `pole_id`, `date`, `shift`, `status`) | public |
| GET | `/api/inventory/{id}` | public |
| POST | `/api/inventory` | admin |
| GET | `/api/tariff/config` | public |
| GET | `/api/poles/{id or code}/price-trend?shift=&date=` | public |
| GET | `/api/dashboard/poles/{code}/analysis` | admin |
| GET | `/api/dashboard/advertiser` | advertiser |
| GET | `/api/dashboard/opportunities` (filters: `date`, `shift`, `category`, `min_footfall`, `min_score`, `max_price`, `round`, `latitude`/`longitude`/`radius_km`) | public (adds your seat when signed in) |
| GET | `/api/users?role=` | admin |
| GET | `/api/poles/{id or code}/footfall-profile?date=` | public |
| GET | `/api/auctions` (filters: `status`, `pole_id`, `date`, `shift`) | public |
| GET | `/api/auctions/{id}` | public |
| POST | `/api/auctions` | admin |
| POST | `/api/auctions/{id}/start` | admin |
| POST | `/api/auctions/{id}/advance` (next round now) | admin |
| POST | `/api/auctions/{id}/complete` (stop now; highest bid wins) | admin |
| GET | `/api/auctions/{id}/bids` | public |
| POST | `/api/auctions/{id}/bids` | advertiser |

## Inventory & tariff

Each pole has twelve 2-hour shifts per day (configurable via `GEOBID_SHIFTS`).
Inventory for the next two days is created by the seed script and topped up on
every backend start. Base prices come from a transparent POC rule:

```
pole_value       = 0.7 × footfall_score + 0.3 × visibility_score
pole_multiplier  = 0.5 + 1.5 × pole_value / 100
avg_slot         = pole's average daily footfall × 2 h / 24 h
slot_multiplier  = (slot_footfall / avg_slot) ^ 0.6, clamped to 0.5–1.8
base price       = ₹3,000 × pole_multiplier × slot_multiplier
```

₹3,000 is the standard rate for a 2-hour shift. `slot_footfall` is the
footfall model's figure for that pole, slot and **weekday**, so each pole's
busiest slots cost the most and a business-corridor pole's weekday evenings
cost more than its Sunday evenings. The 0.6 exponent damps extremes (a slot
with 2× the average footfall costs ~1.5× more). Demand labels (Low → Very
high) come from the same footfall ratio. Example: P014, Saturday
18:00–20:00: 1,254 footfall vs a 705 average slot → 1.41 → ₹3,000 × 1.70 ×
1.41 ≈ ₹7,200. Without an hourly profile, the configured shift demand
multipliers are used as a fallback. Settings: `GEOBID_SLOT_FOOTFALL_EXPONENT`,
`GEOBID_SLOT_MULTIPLIER_MIN`, `GEOBID_SLOT_MULTIPLIER_MAX`. The base price is
only where bidding starts.

## Auctions: 4 rotating seats, two rounds

Each slot (pole + date + 2-hour shift) is a **rolling ad shared by 4
advertisers** in equal rotation; every seat holder pays their own bid.
Bidding is open for the **next 7 days**.

| Round | When (local time) | Bidding |
|-------|-------------------|---------|
| **Qualifying** | until **12:00 the day before** | anyone; the top 4 bidders hold seats 1–4 |
| **Break** | 12:00 → 16:00 | none; **seats 1–2 are confirmed** |
| **Premium** | **16:00 → 2 h before the slot** | anyone (except confirmed holders) from **1.5× the top bid**; premium bids take **seat 4, then seat 3**, then the lowest premium seat |

- Seats are always the top bids per advertiser. To enter when seats are full,
  beat the lowest open seat by ₹100; you can raise your own bid to move up.
- Bids must be at least ₹100 apart from every other seat holder's bid, so
  no two seats hold the same amount.
- Bumped bidders can bid again. At the close every seat holder wins and pays
  their own bid (`winning_advertisements` has one row per seat).
- Seat rules live in `app/services/seat_engine.py` (pure functions). Bids use
  optimistic concurrency (an auction `version`), so simultaneous bids, or a
  bid racing the 12:00 cut-off, can't both apply.
- A background task (every second) applies the 12:00 / 16:00 / close
  transitions. Admins can `POST /api/auctions/{id}/advance` (next round now)
  or `/complete` (close now).
- `GET /api/auctions/{id}` returns the 4 `seats`, and, when signed in, a
  `viewer` block with your seat and the minimum you can bid right now.

**Demo data** (`seed_database --reset`, ~30 s): 8 advertisers; every slot of
every pole for the next 7 days has an auction with bids; a week of completed
auctions. P014 16:00–18:00 tomorrow: advertisers 2–3 hold confirmed seats,
4–5 hold seats 3–4 provisionally, advertiser 1 can take one in the premium
round. Auction times follow the real clock, so reseed on a later day.

## Footfall by time slot

Besides each pole's daily footfall (used for map colours and rankings), the
footfall model outputs **footfall per pole, weekday and hour**
(`footfall_hourly_profile.csv`, read via
`FootfallProvider.get_hourly_profiles`). GeoBid sums the hours inside each
2-hour slot, so slot footfall follows whatever shifts are configured.

The synthetic profile blends two shapes by proximity to business hubs:
business corridors (HITEC City, Gachibowli, Financial District) have weekday
commute peaks and quiet weekends; residential/retail areas (Kondapur,
Madhapur, Miyapur) have a broad evening peak and busier weekends. Hourly values
average out to the pole's daily footfall.

`GET /api/poles/{id}/footfall-profile?date=YYYY-MM-DD` returns footfall per slot
for that date's weekday, the peak slot and per-weekday totals. Inventory slots
and auctions include `slot_footfall`.

## Price history & expected price

`slot_price_history` holds the outcome of every pole × 2-hour shift × day
(winning price, or unsold). Completed auctions write to it; for the POC the
previous **60 days are back-filled synthetically** (weekday pattern with
weekend evenings highest, a gentle upward drift, noise, and unsold days for
low-demand shifts).

The **expected price** for a slot is the average winning price for the same
pole, shift and **weekday** over the last 60 days, shown as a rounded range
roughly 10% wide (step = largest of 10/25/50/100/250/500/1,000/… that is
≤ 12% of the value): ₹425 → ₹400–450, ₹9,430 → ₹9,000–10,000.

`GET /api/poles/{id}/price-trend?shift=S9&date=YYYY-MM-DD` returns the daily
points, per-weekday averages and the expected range for `date`'s weekday.
Inventory slots and auctions also include `expected_price`.

## WebSocket

`ws://localhost:8000/ws/auctions/{auction_id}` (through the Vite proxy in dev:
`ws://localhost:5173/ws/auctions/{auction_id}`). Read-only; bids are placed
with `POST /api/auctions/{id}/bids`.

| Message | When | Key fields |
|---------|------|------------|
| `SNAPSHOT` | on connect | `auction`, `bids` |
| `NEW_BID` | a bid is accepted | `amount`, `bidder_id`, `bidder_alias`, `round`, `seats`, `bid_count`, `next_min_bid`, `timestamp` |
| `OUTBID` | after `NEW_BID`, once per advertiser pushed out of the seats | `outbid_user_id`, `amount`, `next_min_bid` |
| `AUCTION_STARTED` | a scheduled auction goes live | `start_time`, `qualifying_end_time`, `premium_start_time`, `end_time` |
| `QUALIFYING_CLOSED` | 12:00: seats 1–2 confirmed | `seats`, `confirmed_ids`, `premium_floor`, `premium_start_time` |
| `PREMIUM_ROUND_STARTED` | 16:00; anyone may bid for seats 3–4 | `premium_floor`, `end_time` |
| `AUCTION_COMPLETED` | bidding closes | `winners` [{`seat`, `advertiser_id`, `amount`}], `revenue`, `slot_status` |
| `VIEWERS` | someone joins/leaves | `count` |
| `PONG` | reply to `{"type": "PING"}` | |

```json
{"type": "NEW_BID", "auction_id": 1, "amount": 19800, "bidder_id": 4, "bidder_alias": "Bidder 4",
 "bid_count": 4, "next_min_bid": 20300, "timestamp": "2026-10-02T09:52:11.104Z"}
```

Flow: `POST bid` → validation → DB update → auction service returns events →
event bus (single ordered queue) → connection manager → every socket in that
auction's room. The browser reconnects automatically and falls back to REST
polling only while disconnected.

## Dashboards

There are two roles: **advertisers** bid, and the **GeoBid admin** runs the
poles and auctions (there are no separate pole owners). Both start on the map.

- **Admin:** clicking a pole opens its analysis and controls instead of the
  bidding panel: status, slots on sale, revenue, seats sold, sell-through,
  price vs base, then **Auction control** for each 2-hour slot over the next
  7 days: *Open* a scheduled auction, move a live one to its next round
  (*Close qualifying* → *Open premium* → *Close auction*), *End now*, or
  *Create* one for a slot without an auction (two-click confirm). Below that
  are a 30-day revenue chart and footfall/pricing per slot.
- **Advertiser** (`/advertiser/dashboard`): seats held / at risk / won, total
  spend; *My auctions* (the 50 closing soonest, with your seat and what you
  must bid to keep or regain it); *Find inventory* with filters; seats won.
  Bids open the same popup as the map.

## Deployment (Vercel + Render)

The **frontend** is a static Vite app and runs on **Vercel**. The **backend**
needs WebSockets, a background auction worker and a local SQLite file, which
Vercel's serverless functions don't support, so it runs on **Render** (any host
with long-running processes works).

1. **Push this repo to GitHub.**
2. **Backend on Render:** *New → Blueprint*, pick the repo. `render.yaml`
   creates `geobid-api` (free plan): it installs dependencies, **re-seeds the
   demo data on every start** (the free tier's disk resets and demo auctions
   follow the real clock), and serves on `$PORT`. A JWT secret is generated,
   and CORS allows `https://*.vercel.app`. Note the service URL, e.g.
   `https://geobid-api.onrender.com`.
3. **Frontend on Vercel:** *Add New → Project*, import the repo, set
   **Root Directory** to `frontend` (Vite is detected; `vercel.json` adds the
   SPA rewrite), and add the environment variable
   `VITE_API_BASE_URL=https://<your-render-service>.onrender.com`. Deploy.
   The API, WebSocket (`wss://`) and map tiles all go to that URL.

Free-tier notes: Render sleeps after ~15 minutes idle; the first request then
takes about a minute (wake-up plus the ~30 s demo seed), and every wake-up
starts from fresh demo data. For a custom frontend domain, add it to
`GEOBID_CORS_ORIGINS` on Render as a JSON list.

## Demo accounts

Password for all: `geobid123`

| Role       | Email                      |
|------------|----------------------------|
| Admin      | admin@geobid.local         |
| Advertiser | advertiser1@geobid.local   |
| Advertiser | advertiser2@geobid.local   |
| Advertiser | advertiser3@geobid.local   |

## Configuration

Copy `.env.example` to `.env`. Backend settings use the `GEOBID_` prefix.
