import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '@/contexts/auth-context'
import { Skeleton } from '@/components/ui/skeleton'

export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen bg-background flex flex-col gap-4 p-8">
        <Skeleton className="h-16 w-full" />
        <div className="flex gap-4 flex-1">
          <Skeleton className="h-full w-60" />
          <Skeleton className="h-full flex-1" />
        </div>
      </div>
    )
  }

  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />
}
