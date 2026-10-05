import { BrowserRouter, Navigate, Route, Routes } from 'react-router'

import { AppShell } from '@/components/layout/AppShell'
import { RequireRole } from '@/components/layout/RequireRole'
import { AuthProvider } from '@/hooks/useAuth'
import { ToastProvider } from '@/hooks/useToast'
import { AdminFinancePage } from '@/pages/AdminFinancePage'
import { AdvertiserDashboardPage } from '@/pages/AdvertiserDashboardPage'
import { AuctionPage } from '@/pages/AuctionPage'
import { LoginPage } from '@/pages/LoginPage'
import { MapPage } from '@/pages/MapPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { PoleDetailsPage } from '@/pages/PoleDetailsPage'
import { SignupPage } from '@/pages/SignupPage'
import { VideosPage } from '@/pages/VideosPage'

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route element={<AppShell />}>
              <Route index element={<Navigate to="/map" replace />} />
              <Route path="map" element={<MapPage />} />
              <Route path="poles/:id" element={<PoleDetailsPage />} />
              <Route path="auctions/:id" element={<AuctionPage />} />
              <Route path="login" element={<LoginPage />} />
              <Route path="signup" element={<SignupPage />} />
              <Route path="videos" element={<VideosPage />} />
              <Route path="admin/finance" element={<RequireRole roles={['ADMIN']}><AdminFinancePage /></RequireRole>} />
              <Route path="advertiser/dashboard" element={<RequireRole roles={['ADVERTISER']}><AdvertiserDashboardPage /></RequireRole>} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  )
}
