import { useQuery } from '@tanstack/react-query'
import { FileText, Briefcase, BarChart3, TrendingUp, Plus, ArrowRight } from 'lucide-react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { AnalysisStatusBadge } from '@/components/features/analysis-status-badge'
import { analysisApi } from '@/api/analysis'
import { resumesApi } from '@/api/resumes'
import { jobsApi } from '@/api/jobs'
import { formatDate, scoreColor } from '@/lib/utils'

const FADE = { hidden: { opacity: 0, y: 16 }, show: { opacity: 1, y: 0 } }
const STAGGER = { show: { transition: { staggerChildren: 0.08 } } }

function StatCard({ icon: Icon, label, value, color, isLoading }: { icon: React.ElementType; label: string; value: string | number; color: string; isLoading?: boolean }) {
  return (
    <motion.div variants={FADE}>
      <Card className="hover:border-primary/30 transition-colors">
        <CardContent className="pt-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">{label}</p>
              {isLoading ? (
                <Skeleton className="h-9 w-16 mt-1" />
              ) : (
                <p className="text-3xl font-bold mt-1">{value}</p>
              )}
            </div>
            <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${color}`}>
              <Icon className="h-6 w-6" />
            </div>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

export default function DashboardPage() {
  // Fetch resume count
  const { data: resumesData, isLoading: resumesLoading } = useQuery({
    queryKey: ['resumes', 'list', 'dashboard'],
    queryFn: () => resumesApi.list(1, 0),
    refetchInterval: 30_000,
  })

  // Fetch jobs
  const { data: jobs, isLoading: jobsLoading } = useQuery({
    queryKey: ['jobs', 'list'],
    queryFn: () => jobsApi.list(100, 0),
    refetchInterval: 30_000,
  })

  // Fetch analysis stats
  const { data: analysisStats, isLoading: statsLoading } = useQuery({
    queryKey: ['analysis', 'stats'],
    queryFn: () => analysisApi.stats(),
    refetchInterval: 15_000,
  })

  // Fetch recent analyses
  const { data: recentAnalyses, isLoading: analysesLoading } = useQuery({
    queryKey: ['analysis', 'list', 'dashboard'],
    queryFn: () => analysisApi.list(5, 0),
    refetchInterval: 10_000,
  })

  const totalResumes = resumesData?.total_count ?? 0
  const totalJobs = jobs?.total_count ?? 0
  const totalAnalyses = analysisStats?.total_analyses ?? 0
  const avgScore = analysisStats?.avg_score != null ? Math.round(analysisStats.avg_score) : '—'

  return (
    <div className="space-y-8">
      {/* Stats */}
      <motion.div
        variants={STAGGER}
        initial="hidden"
        animate="show"
        className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
      >
        <StatCard icon={FileText} label="Resumes" value={totalResumes} color="bg-indigo-500/10 text-indigo-500" isLoading={resumesLoading} />
        <StatCard icon={Briefcase} label="Job Descriptions" value={totalJobs} color="bg-violet-500/10 text-violet-500" isLoading={jobsLoading} />
        <StatCard icon={BarChart3} label="Analyses Run" value={totalAnalyses} color="bg-emerald-500/10 text-emerald-500" isLoading={statsLoading} />
        <StatCard icon={TrendingUp} label="Avg. Match Score" value={avgScore === '—' ? avgScore : `${avgScore}%`} color="bg-amber-500/10 text-amber-500" isLoading={statsLoading} />
      </motion.div>

      {/* Quick actions */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3 }}>
        <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider mb-4">Quick Actions</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[
            { to: '/resumes', icon: FileText, label: 'Upload a Resume', desc: 'Parse and store a candidate CV' },
            { to: '/jobs', icon: Briefcase, label: 'Add a Job Description', desc: 'Create a JD for matching' },
            { to: '/analysis', icon: BarChart3, label: 'Start an Analysis', desc: 'Match a resume to a JD' },
          ].map(({ to, icon: Icon, label, desc }) => (
            <Link key={to} to={to}>
              <Card className="h-full hover:border-primary/40 hover:bg-accent/30 transition-all cursor-pointer group">
                <CardContent className="pt-6 pb-5">
                  <div className="flex items-start justify-between">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
                      <Icon className="h-5 w-5 text-primary" />
                    </div>
                    <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                  </div>
                  <p className="font-semibold text-sm mt-3">{label}</p>
                  <p className="text-xs text-muted-foreground mt-1">{desc}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </motion.div>

      {/* Recent analyses */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.35 }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Recent Analyses</h2>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/analysis">View all <ArrowRight className="h-3.5 w-3.5 ml-1" /></Link>
          </Button>
        </div>
        <Card>
          {analysesLoading ? (
            <CardContent className="pt-6 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </CardContent>
          ) : !recentAnalyses?.items.length ? (
            <CardContent className="pt-6 pb-8 text-center">
              <BarChart3 className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No analyses yet.</p>
              <Button size="sm" className="mt-3" asChild>
                <Link to="/analysis"><Plus className="h-4 w-4 mr-1" />Run one</Link>
              </Button>
            </CardContent>
          ) : (
            <div className="divide-y divide-border">
              {recentAnalyses.items.map(a => (
                <div key={a.id} className="flex items-center justify-between px-6 py-3">
                  <div className="flex items-center gap-3">
                    <div>
                      <p className="text-sm font-medium font-mono">#{a.id.slice(0, 8)}</p>
                      <p className="text-xs text-muted-foreground">{formatDate(a.created_at)}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    {a.score_composite != null && (
                      <span className={`text-sm font-bold ${scoreColor(a.score_composite)}`}>
                        {Math.round(a.score_composite)}%
                      </span>
                    )}
                    <AnalysisStatusBadge status={a.status} />
                    <Button variant="ghost" size="sm" asChild>
                      <Link to={`/analysis/${a.id}`}>View</Link>
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>

      {/* Recent jobs */}
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.4 }}>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Recent Job Descriptions</h2>
          <Button variant="ghost" size="sm" asChild>
            <Link to="/jobs">View all <ArrowRight className="h-3.5 w-3.5 ml-1" /></Link>
          </Button>
        </div>
        <Card>
          {jobsLoading ? (
            <CardContent className="pt-6 space-y-3">
              {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </CardContent>
          ) : !jobs?.items.length ? (
            <CardContent className="pt-6 pb-8 text-center">
              <Briefcase className="h-10 w-10 text-muted-foreground/40 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">No job descriptions yet.</p>
              <Button size="sm" className="mt-3" asChild>
                <Link to="/jobs"><Plus className="h-4 w-4 mr-1" />Add one</Link>
              </Button>
            </CardContent>
          ) : (
            <div className="divide-y divide-border">
              {jobs.items.slice(0, 5).map(jd => (
                <div key={jd.id} className="flex items-center justify-between px-6 py-3">
                  <div>
                    <p className="text-sm font-medium">{jd.title}</p>
                    <p className="text-xs text-muted-foreground">{jd.company ?? 'Unknown company'} · {formatDate(jd.created_at)}</p>
                  </div>
                  <Button variant="ghost" size="sm" asChild>
                    <Link to={`/jobs?id=${jd.id}`}>View</Link>
                  </Button>
                </div>
              ))}
            </div>
          )}
        </Card>
      </motion.div>
    </div>
  )
}
