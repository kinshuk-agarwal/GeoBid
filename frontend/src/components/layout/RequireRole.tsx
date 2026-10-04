import { Navigate, useLocation } from 'react-router'

import { useAuth } from '@/hooks/useAuth'
import type { Role } from '@/types'

import { Spinner } from '../common/Spinner'

export const HOME_FOR: Record<Role, string> = {
  ADVERTISER: '/advertiser/dashboard',
  ADMIN: '/map', // admins analyse poles on the map
}

/** Render children only for signed-in users with one of ``roles``. */
export function RequireRole({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const location = useLocation()
  if (loading) {
    return (
      <div className="flex justify-center p-10">
        <Spinner className="size-6" />
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (!roles.includes(user.role)) return <Navigate to={HOME_FOR[user.role]} replace />
  return <>{children}</>
}
