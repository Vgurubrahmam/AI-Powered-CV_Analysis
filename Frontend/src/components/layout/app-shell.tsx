import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { Sidebar, MobileSidebar } from './sidebar'
import { Header } from './header'

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/resumes': 'Resumes',
  '/jobs': 'Job Descriptions',
  '/analysis': 'Analyses',
  '/profile': 'Profile',
}

function getTitle(pathname: string): string {
  // Try exact match first, then prefix match
  if (pageTitles[pathname]) return pageTitles[pathname]
  for (const [key, label] of Object.entries(pageTitles)) {
    if (pathname.startsWith(key)) return label
  }
  return 'ResumeAI'
}

export function AppShell() {
  const { pathname } = useLocation()
  const title = getTitle(pathname)
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <MobileSidebar open={mobileOpen} onOpenChange={setMobileOpen} />
      <div className="md:pl-[var(--sidebar-width)] flex flex-col min-h-screen">
        <Header title={title} onMobileMenuClick={() => setMobileOpen(true)} />
        <main className="flex-1 p-6 max-w-screen-2xl">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
