import { Link } from 'react-router'

export function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-8 text-center">
      <p className="text-sm font-semibold text-slate-400">404</p>
      <h1 className="text-lg font-semibold">Page not found</h1>
      <Link to="/map" className="text-sm font-medium text-slate-700 underline underline-offset-2">
        Back to the map
      </Link>
    </div>
  )
}
