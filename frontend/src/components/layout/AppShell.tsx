import { Film, IndianRupee, LayoutDashboard, LogIn, LogOut, MapPinned } from 'lucide-react'
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router'

import { useAuth } from '@/hooks/useAuth'

import { HOME_FOR } from './RequireRole'

const ROLE_LABEL = { ADVERTISER: 'Advertiser', ADMIN: 'Admin' } as const

function navClass({ isActive }: { isActive: boolean }) {
  return `inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
    isActive ? 'bg-slate-900 text-white' : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`
}

export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  return (
    <div className="flex h-full flex-col">
      <header className="z-[1100] flex h-14 shrink-0 items-center gap-4 border-b border-slate-200 bg-white px-4">
        <Link to="/map" className="flex items-center gap-2">
          <img src="/favicon.svg" alt="" className="size-7" />
          <span className="text-[15px] font-semibold tracking-tight">GeoBid</span>
        </Link>

        <nav className="flex items-center gap-1">
          <NavLink to="/map" className={navClass}>
            <MapPinned className="size-4" />
            Map
          </NavLink>
          {user?.role === 'ADMIN' && (
            <NavLink to="/admin/finance" className={navClass}>
              <IndianRupee className="size-4" />
              Finance
            </NavLink>
          )}
          <NavLink to="/videos" className={navClass}>
            <Film className="size-4" />
            Videos
          </NavLink>
          {user && HOME_FOR[user.role] !== '/map' && (
            <NavLink to={HOME_FOR[user.role]} className={navClass}>
              <LayoutDashboard className="size-4" />
              Dashboard
            </NavLink>
          )}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {user ? (
            <>
              <div className="hidden text-right leading-tight sm:block">
                <div className="text-sm font-medium">{user.name}</div>
                <div className="text-xs text-slate-500">{ROLE_LABEL[user.role]}</div>
              </div>
              <button
                onClick={() => {
                  logout()
                  navigate('/map')
                }}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-200 px-2.5 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
              >
                <LogOut className="size-4" />
                <span className="hidden sm:inline">Sign out</span>
              </button>
            </>
          ) : (
            <>
            <Link
              to="/signup"
              state={{ from: location.pathname + location.search }}
              className="hidden rounded-md px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 sm:inline-flex"
            >
              Sign up
            </Link>
            <Link
              to="/login"
              state={{ from: location.pathname + location.search }}
              className="inline-flex items-center gap-1.5 rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-800"
            >
              <LogIn className="size-4" />
              Sign in
            </Link>
            </>
          )}
        </div>
      </header>

      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}
