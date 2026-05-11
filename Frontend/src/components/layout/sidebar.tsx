import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard, FileText, Briefcase, BarChart3, User, BrainCircuit,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Sheet, SheetContent } from '@/components/ui/sheet'

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/resumes', label: 'Resumes', icon: FileText },
  { to: '/jobs', label: 'Job Descriptions', icon: Briefcase },
  { to: '/analysis', label: 'Analyses', icon: BarChart3 },
  { to: '/profile', label: 'Profile', icon: User },
]

function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
      {navItems.map(({ to, label, icon: Icon }) => (
        <NavLink
          key={to}
          to={to}
          onClick={onNavigate}
          className={({ isActive }) =>
            cn(
              'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
              isActive
                ? 'bg-primary/10 text-primary'
                : 'text-muted-foreground hover:bg-accent hover:text-foreground',
            )
          }
        >
          <Icon className="h-4 w-4 shrink-0" />
          {label}
        </NavLink>
      ))}
    </nav>
  )
}

function SidebarLogo() {
  return (
    <div className="flex items-center gap-2.5 px-5 h-16 border-b border-border shrink-0">
      <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
        <BrainCircuit className="h-4 w-4 text-white" />
      </div>
      <div>
        <p className="text-sm font-semibold leading-none">ResumeAI</p>
        <p className="text-[10px] text-muted-foreground mt-0.5">ATS Platform</p>
      </div>
    </div>
  )
}

export function Sidebar() {
  return (
    <aside className="hidden md:flex flex-col h-screen w-[var(--sidebar-width)] border-r border-border bg-card fixed left-0 top-0 z-30">
      <SidebarLogo />
      <SidebarNav />
      {/* Footer version */}
      <div className="px-5 py-3 border-t border-border">
        <p className="text-[10px] text-muted-foreground">v1.0.0 — Enterprise</p>
      </div>
    </aside>
  )
}

export function MobileSidebar({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="left" className="w-[260px] p-0">
        <div className="flex flex-col h-full">
          <SidebarLogo />
          <SidebarNav onNavigate={() => onOpenChange(false)} />
          <div className="px-5 py-3 border-t border-border">
            <p className="text-[10px] text-muted-foreground">v1.0.0 — Enterprise</p>
          </div>
        </div>
      </SheetContent>
    </Sheet>
  )
}
