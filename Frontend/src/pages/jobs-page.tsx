import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Briefcase, Eye, ChevronLeft, ChevronRight, Building2 } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { motion } from 'framer-motion'
import { jobsApi } from '@/api/jobs'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { formatDate } from '@/lib/utils'
import type { JDRead, ParsedJDRead } from '@/types/job'

const PAGE_SIZE = 10

const schema = z.object({
  title: z.string().min(2, 'Title is required'),
  company: z.string().optional(),
  raw_text: z.string().min(50, 'Description must be at least 50 characters'),
})
type FormData = z.infer<typeof schema>

export default function JobsPage() {
  const qc = useQueryClient()
  const [page, setPage] = useState(0)
  const [showCreate, setShowCreate] = useState(false)
  const [viewJob, setViewJob] = useState<JDRead | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['jobs', 'list', page],
    queryFn: () => jobsApi.list(PAGE_SIZE, page * PAGE_SIZE),
    staleTime: 60_000,
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? []
      const hasPending = items.some((j) => j.parse_status === 'PENDING')
      return hasPending ? 3000 : false
    },
  })

  const { data: parsedJob } = useQuery({
    queryKey: ['jobs', viewJob?.id, 'parsed'],
    queryFn: () => jobsApi.getParsed(viewJob!.id),
    enabled: !!viewJob && viewJob.parse_status === 'SUCCESS',
  })

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(schema),
  })

  const createMutation = useMutation({
    mutationFn: (data: FormData) => jobsApi.create(data),
    onSuccess: () => {
      toast.success('Job description created')
      qc.invalidateQueries({ queryKey: ['jobs', 'list'] })
      setShowCreate(false)
      reset()
    },
    onError: () => toast.error('Failed to create job description'),
  })

  const totalPages = Math.ceil((data?.total_count ?? 0) / PAGE_SIZE)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Job Descriptions</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {data ? `${data.total_count} total` : 'Loading…'}
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>
          <Plus className="h-4 w-4" />
          New Job
        </Button>
      </div>

      {/* Create dialog */}
      <Dialog open={showCreate} onOpenChange={v => { setShowCreate(v); if (!v) reset() }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>New Job Description</DialogTitle>
            <DialogDescription>Fill in the details. The JD will be parsed by AI asynchronously.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(d => createMutation.mutate(d))} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2 col-span-2">
                <Label htmlFor="title">Job Title *</Label>
                <Input id="title" placeholder="Senior Software Engineer" {...register('title')} />
                {errors.title && <p className="text-xs text-destructive">{errors.title.message}</p>}
              </div>
              <div className="space-y-2">
                <Label htmlFor="company">Company</Label>
                <Input id="company" placeholder="Acme Corp" {...register('company')} />
              </div>
              <div className="space-y-2 col-span-2">
                <Label htmlFor="raw_text">Job Description *</Label>
                <Textarea id="raw_text" placeholder="Paste the full job description here…" rows={8} {...register('raw_text')} />
                {errors.raw_text && <p className="text-xs text-destructive">{errors.raw_text.message}</p>}
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => { setShowCreate(false); reset() }}>Cancel</Button>
              <Button type="submit" disabled={isSubmitting || createMutation.isPending}>
                {createMutation.isPending ? 'Creating…' : 'Create Job'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Detail sheet */}
      <Sheet open={!!viewJob} onOpenChange={() => setViewJob(null)}>
        <SheetContent className="w-full sm:max-w-lg p-6">
          <SheetHeader>
            <SheetTitle>{viewJob?.title}</SheetTitle>
            <SheetDescription>{viewJob?.company ?? ''}</SheetDescription>
          </SheetHeader>
          {viewJob && <JobDetailPanel job={viewJob} parsed={parsedJob ?? null} />}
        </SheetContent>
      </Sheet>

      {/* Table */}
      {isLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 5 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}
        </div>
      ) : !data?.items.length ? (
        <EmptyState onAdd={() => setShowCreate(true)} />
      ) : (
        <div className="space-y-3">
          {data.items.map(jd => (
            <motion.div key={jd.id} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
              <Card className="hover:border-border/80 transition-colors">
                <CardContent className="flex items-center gap-4 py-4 px-5">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-500/10">
                    <Briefcase className="h-5 w-5 text-violet-500" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{jd.title}</p>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
                      {jd.company && <span className="flex items-center gap-1"><Building2 className="h-3 w-3" />{jd.company}</span>}
                      <span>{formatDate(jd.created_at)}</span>
                    </div>
                  </div>
                  <Badge variant={jd.parse_status === 'SUCCESS' ? 'success' : jd.parse_status === 'FAILED' ? 'destructive' : 'muted'}>
                    {jd.parse_status}
                  </Badge>
                  <Button variant="ghost" size="icon" onClick={() => setViewJob(jd)} aria-label="View job">
                    <Eye className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            </motion.div>
          ))}

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-3 pt-2">
              <Button variant="outline" size="sm" onClick={() => setPage(p => p - 1)} disabled={page === 0}>
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-sm text-muted-foreground">Page {page + 1} / {totalPages}</span>
              <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={page >= totalPages - 1}>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function JobDetailPanel({ job, parsed }: { job: JDRead; parsed: ParsedJDRead | null }) {
  return (
    <div className="space-y-6 mt-2">
      <div>
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Description</p>
        <p className="text-sm text-muted-foreground leading-relaxed line-clamp-6">{job.raw_text ?? '(not available)'}</p>
      </div>
      <Separator />
      {parsed?.parsed_data ? (
        <>
          {parsed.parsed_data.required_skills.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Required Skills</p>
              <div className="flex flex-wrap gap-1.5">
                {parsed.parsed_data.required_skills.map(s => <Badge key={s} variant="default">{s}</Badge>)}
              </div>
            </div>
          )}
          {parsed.parsed_data.preferred_skills.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Preferred Skills</p>
              <div className="flex flex-wrap gap-1.5">
                {parsed.parsed_data.preferred_skills.map(s => <Badge key={s} variant="secondary">{s}</Badge>)}
              </div>
            </div>
          )}
          {(parsed.parsed_data.years_experience_required?.min != null || parsed.parsed_data.years_experience_required?.max != null) && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Experience Required</p>
              <p className="text-sm">{parsed.parsed_data.years_experience_required?.min ?? 0}–{parsed.parsed_data.years_experience_required?.max ?? '?'} years</p>
            </div>
          )}
          {parsed.parsed_data.responsibilities.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Key Responsibilities</p>
              <ul className="space-y-1.5">
                {parsed.parsed_data.responsibilities.map((r, i) => (
                  <li key={i} className="text-sm text-muted-foreground flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <p className="text-sm text-muted-foreground italic">
          {job.parse_status === 'PENDING'
            ? 'Parsed data will appear here once processing is complete.'
            : 'Parsing failed for this job description.'}
        </p>
      )}
    </div>
  )
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-border py-20 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <Briefcase className="h-8 w-8 text-muted-foreground/50" />
      </div>
      <div>
        <p className="font-semibold">No job descriptions yet</p>
        <p className="text-sm text-muted-foreground mt-1">Create your first job description to enable matching</p>
      </div>
      <Button onClick={onAdd}><Plus className="h-4 w-4" />New Job</Button>
    </div>
  )
}
