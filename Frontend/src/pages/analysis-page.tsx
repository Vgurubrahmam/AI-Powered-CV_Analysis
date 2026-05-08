import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, BarChart3, ArrowRight, Loader2 } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { motion } from 'framer-motion'
import { analysisApi } from '@/api/analysis'
import { resumesApi } from '@/api/resumes'
import { jobsApi } from '@/api/jobs'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { AnalysisStatusBadge } from '@/components/features/analysis-status-badge'
import { formatDateTime } from '@/lib/utils'
import type { AnalysisRead } from '@/types/analysis'

export default function AnalysisPage() {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [showWizard, setShowWizard] = useState(false)
  const [selectedResume, setSelectedResume] = useState('')
  const [selectedJob, setSelectedJob] = useState('')

  // Fetch analyses from API (no more localStorage!)
  const { data: analysesData, isLoading: analysesLoading } = useQuery({
    queryKey: ['analysis', 'list'],
    queryFn: () => analysisApi.list(100, 0),
    refetchInterval: (query) => {
      // Auto-refresh while any analysis is in progress
      const items = query.state.data?.items ?? []
      const hasInProgress = items.some(a => !['DONE', 'FAILED'].includes(a.status))
      return hasInProgress ? 5000 : false
    },
  })

  const analyses = analysesData?.items ?? []

  // Fetch resumes from API for the select dropdown
  const { data: resumesData } = useQuery({
    queryKey: ['resumes', 'list', 'for-analysis'],
    queryFn: () => resumesApi.list(100, 0),
    enabled: showWizard,
  })

  const { data: jobsData } = useQuery({
    queryKey: ['jobs', 'list', 'for-analysis'],
    queryFn: () => jobsApi.list(100, 0),
    enabled: showWizard,
  })

  const createMutation = useMutation({
    mutationFn: () => analysisApi.create({ resume_id: selectedResume, job_id: selectedJob }),
    onSuccess: () => {
      setShowWizard(false)
      setSelectedResume('')
      setSelectedJob('')
      toast.success('Analysis queued. Processing…')
      qc.invalidateQueries({ queryKey: ['analysis'] })
    },
    onError: () => toast.error('Failed to start analysis'),
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Analyses</h1>
          <p className="text-sm text-muted-foreground mt-0.5">AI-powered resume-to-job matching</p>
        </div>
        <Button onClick={() => setShowWizard(true)}>
          <Plus className="h-4 w-4" />
          New Analysis
        </Button>
      </div>

      {/* New Analysis wizard */}
      <Dialog open={showWizard} onOpenChange={setShowWizard}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Start New Analysis</DialogTitle>
            <DialogDescription>Select a resume and job description to match</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label className="text-sm font-medium">Resume</label>
              {!resumesData?.items.length ? (
                <p className="text-xs text-muted-foreground italic">No resumes found. Upload one first.</p>
              ) : (
                <Select value={selectedResume} onValueChange={setSelectedResume}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a resume…" />
                  </SelectTrigger>
                  <SelectContent>
                    {resumesData.items.map(r => (
                      <SelectItem key={r.id} value={r.id}>
                        {r.file_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Job Description</label>
              {!jobsData?.items.length ? (
                <p className="text-xs text-muted-foreground italic">No jobs found. Create one first.</p>
              ) : (
                <Select value={selectedJob} onValueChange={setSelectedJob}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a job…" />
                  </SelectTrigger>
                  <SelectContent>
                    {jobsData.items.map(jd => (
                      <SelectItem key={jd.id} value={jd.id}>{jd.title}{jd.company ? ` — ${jd.company}` : ''}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowWizard(false)}>Cancel</Button>
            <Button
              onClick={() => createMutation.mutate()}
              disabled={!selectedResume || !selectedJob || createMutation.isPending}
            >
              {createMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
              Run Analysis
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Analysis list */}
      {analysesLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}
        </div>
      ) : analyses.length === 0 ? (
        <EmptyState onNew={() => setShowWizard(true)} />
      ) : (
        <div className="space-y-3">
          {analyses.map(analysis => (
            <AnalysisRow key={analysis.id} analysis={analysis} onOpen={() => navigate(`/analysis/${analysis.id}`)} />
          ))}
        </div>
      )}
    </div>
  )
}

function AnalysisRow({ analysis, onOpen }: { analysis: AnalysisRead; onOpen: () => void }) {
  const isDone = analysis.status === 'DONE'
  const isFailed = analysis.status === 'FAILED'

  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="hover:border-border/80 transition-colors">
        <CardContent className="flex items-center gap-4 py-4 px-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10">
            <BarChart3 className="h-5 w-5 text-emerald-500" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium font-mono truncate">#{analysis.id.slice(0, 8)}</p>
            <p className="text-xs text-muted-foreground mt-0.5">{formatDateTime(analysis.created_at)}</p>
          </div>
          {analysis.score_composite != null && (
            <div className="text-right">
              <p className="text-xl font-bold text-primary">{Math.round(analysis.score_composite)}%</p>
              <p className="text-xs text-muted-foreground">match</p>
            </div>
          )}
          <AnalysisStatusBadge status={analysis.status} />
          <Button
            variant="ghost"
            size="icon"
            onClick={onOpen}
            aria-label="View analysis"
            disabled={isFailed}
          >
            <ArrowRight className="h-4 w-4" />
          </Button>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function EmptyState({ onNew }: { onNew: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-border py-20 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <BarChart3 className="h-8 w-8 text-muted-foreground/50" />
      </div>
      <div>
        <p className="font-semibold">No analyses yet</p>
        <p className="text-sm text-muted-foreground mt-1">Upload a resume and a job to start matching</p>
      </div>
      <Button onClick={onNew}><Plus className="h-4 w-4" />New Analysis</Button>
    </div>
  )
}
