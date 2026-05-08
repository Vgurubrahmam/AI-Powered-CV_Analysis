import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, FileText, Trash2, Eye, CheckCircle, Clock, XCircle, AlertCircle } from 'lucide-react'
import { toast } from 'sonner'
import { motion } from 'framer-motion'
import { resumesApi } from '@/api/resumes'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from '@/components/ui/sheet'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'
import { UploadDropzone } from '@/components/features/upload-dropzone'
import { Separator } from '@/components/ui/separator'
import { formatDate, formatFileSize } from '@/lib/utils'
import type { ResumeRead, ParseStatus, ParsedResumeRead } from '@/types/resume'

const statusConfig: Record<ParseStatus, { label: string; icon: React.ElementType; variant: 'success' | 'info' | 'destructive' | 'muted' }> = {
  PENDING:  { label: 'Pending',  icon: Clock,         variant: 'muted' },
  SUCCESS:  { label: 'Parsed',   icon: CheckCircle,   variant: 'success' },
  PARTIAL:  { label: 'Partial',  icon: AlertCircle,   variant: 'info' },
  FAILED:   { label: 'Failed',   icon: XCircle,       variant: 'destructive' },
}

export default function ResumesPage() {
  const qc = useQueryClient()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [showUpload, setShowUpload] = useState(false)
  const [viewResume, setViewResume] = useState<ResumeRead | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null)

  // Fetch resumes from API (no more localStorage!)
  const { data: resumesData, isLoading: resumesLoading } = useQuery({
    queryKey: ['resumes', 'list'],
    queryFn: () => resumesApi.list(100, 0),
  })

  const resumes = resumesData?.items ?? []

  const uploadMutation = useMutation({
    mutationFn: (file: File) => resumesApi.upload(file),
    onSuccess: () => {
      setShowUpload(false)
      setSelectedFile(null)
      toast.success('Resume uploaded and queued for parsing')
      qc.invalidateQueries({ queryKey: ['resumes'] })
    },
    onError: () => toast.error('Upload failed. Please try again.'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => resumesApi.delete(id),
    onSuccess: () => {
      setDeleteTarget(null)
      toast.success('Resume deleted')
      qc.invalidateQueries({ queryKey: ['resumes'] })
    },
    onError: () => toast.error('Delete failed'),
  })

  const { data: parsedData } = useQuery({
    queryKey: ['resumes', viewResume?.id, 'parsed'],
    queryFn: () => resumesApi.getParsed(viewResume!.id),
    enabled: !!viewResume && viewResume.parse_status === 'SUCCESS',
  })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Resumes</h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            {resumesData ? `${resumesData.total_count} total` : 'Upload and manage candidate resumes'}
          </p>
        </div>
        <Button onClick={() => setShowUpload(true)}>
          <Plus className="h-4 w-4" />
          Upload Resume
        </Button>
      </div>

      {/* Upload dialog */}
      <Dialog open={showUpload} onOpenChange={setShowUpload}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Upload Resume</DialogTitle>
            <DialogDescription>PDF, DOCX, or TXT — max 10 MB. Parsed asynchronously.</DialogDescription>
          </DialogHeader>
          <UploadDropzone
            onFileSelected={f => setSelectedFile(f)}
            isUploading={uploadMutation.isPending}
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowUpload(false)}>Cancel</Button>
            <Button
              disabled={!selectedFile || uploadMutation.isPending}
              onClick={() => selectedFile && uploadMutation.mutate(selectedFile)}
            >
              {uploadMutation.isPending ? 'Uploading…' : 'Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirm */}
      <Dialog open={!!deleteTarget} onOpenChange={() => setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Resume</DialogTitle>
            <DialogDescription>This will permanently delete the resume and its S3 file. This cannot be undone.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>Cancel</Button>
            <Button
              variant="destructive"
              disabled={deleteMutation.isPending}
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget)}
            >
              {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Resume detail sheet */}
      <Sheet open={!!viewResume} onOpenChange={() => setViewResume(null)}>
        <SheetContent className="p-6">
          <SheetHeader>
            <SheetTitle>{viewResume?.file_name}</SheetTitle>
            <SheetDescription>Parsed resume data</SheetDescription>
          </SheetHeader>
          {viewResume && <ResumeDetailPanel resume={viewResume} parsed={parsedData ?? null} />}
        </SheetContent>
      </Sheet>

      {/* Resume list */}
      {resumesLoading ? (
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-16 w-full rounded-xl" />)}
        </div>
      ) : resumes.length === 0 ? (
        <EmptyState onUpload={() => setShowUpload(true)} />
      ) : (
        <div className="grid gap-3">
          {resumes.map(resume => (
            <ResumeRow
              key={resume.id}
              resume={resume}
              onView={setViewResume}
              onDelete={setDeleteTarget}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ResumeRow({ resume, onView, onDelete }: { resume: ResumeRead; onView: (r: ResumeRead) => void; onDelete: (id: string) => void }) {
  const cfg = statusConfig[resume.parse_status]
  const Icon = cfg.icon

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
      <Card className="hover:border-border/80 transition-colors">
        <CardContent className="flex items-center gap-4 py-4 px-5">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
            <FileText className="h-5 w-5 text-primary" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium truncate">{resume.file_name}</p>
            <p className="text-xs text-muted-foreground">
              {formatDate(resume.created_at)}
              {resume.file_size_bytes ? ` · ${formatFileSize(resume.file_size_bytes)}` : ''}
              {resume.parse_confidence != null ? ` · Confidence: ${Math.round(resume.parse_confidence * 100)}%` : ''}
            </p>
          </div>
          <Badge variant={cfg.variant}>
            <Icon className="h-3 w-3" />
            {cfg.label}
          </Badge>
          <div className="flex gap-1 shrink-0">
            <Button variant="ghost" size="icon" onClick={() => onView(resume)} aria-label="View">
              <Eye className="h-4 w-4" />
            </Button>
            <Button variant="ghost" size="icon" onClick={() => onDelete(resume.id)} aria-label="Delete"
              className="text-destructive hover:text-destructive">
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>
    </motion.div>
  )
}

function ResumeDetailPanel({ resume, parsed }: { resume: ResumeRead; parsed: ParsedResumeRead | null }) {
  if (resume.parse_status !== 'SUCCESS' || !parsed || !parsed.parsed_data) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
        <AlertCircle className="h-10 w-10 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">
          {resume.parse_status === 'FAILED' ? 'Parsing failed for this resume.' : 'Resume is still being parsed…'}
        </p>
      </div>
    )
  }
  const pd = parsed.parsed_data
  return (
    <div className="space-y-6 mt-2">
      {pd.skills.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {pd.skills.map(s => <Badge key={s} variant="secondary">{s}</Badge>)}
          </div>
        </div>
      )}
      {pd.total_yoe != null && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Experience</p>
          <p className="text-sm">{pd.total_yoe} years</p>
        </div>
      )}
      {pd.education.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Education</p>
          <ul className="space-y-1">
            {pd.education.map((e, i) => <li key={i} className="text-sm">{e.degree} — {e.institution}</li>)}
          </ul>
        </div>
      )}
      {pd.sections_detected.length > 0 && (
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Sections Detected</p>
          <div className="flex flex-wrap gap-1.5">
            {pd.sections_detected.map(s => <Badge key={s} variant="secondary">{s}</Badge>)}
          </div>
        </div>
      )}
    </div>
  )
}

function EmptyState({ onUpload }: { onUpload: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed border-border py-20 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-muted">
        <FileText className="h-8 w-8 text-muted-foreground/50" />
      </div>
      <div>
        <p className="font-semibold">No resumes yet</p>
        <p className="text-sm text-muted-foreground mt-1">Upload your first resume to get started</p>
      </div>
      <Button onClick={onUpload}>
        <Plus className="h-4 w-4" />
        Upload Resume
      </Button>
    </div>
  )
}
