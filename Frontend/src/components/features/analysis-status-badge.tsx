import { Badge } from '@/components/ui/badge'
import type { AnalysisStatus } from '@/types/analysis'
import type { BadgeProps } from '@/components/ui/badge'

const STATUS_MAP: Record<AnalysisStatus, { label: string; variant: BadgeProps['variant'] }> = {
  QUEUED:   { label: 'Queued',   variant: 'muted' },
  PARSING:  { label: 'Parsing',  variant: 'info' },
  MATCHING: { label: 'Matching', variant: 'info' },
  SCORING:  { label: 'Scoring',  variant: 'info' },
  FEEDBACK: { label: 'Feedback', variant: 'info' },
  DONE:     { label: 'Done',     variant: 'success' },
  PARTIAL:  { label: 'Partial',  variant: 'warning' },
  FAILED:   { label: 'Failed',   variant: 'destructive' },
}

export function AnalysisStatusBadge({ status }: { status: AnalysisStatus }) {
  const { label, variant } = STATUS_MAP[status] ?? { label: status, variant: 'outline' }
  const isPulsing = ['PARSING', 'MATCHING', 'SCORING'].includes(status)
  return (
    <Badge variant={variant} className="gap-1.5">
      {isPulsing && (
        <span className="relative flex h-1.5 w-1.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
          <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-blue-500" />
        </span>
      )}
      {label}
    </Badge>
  )
}
