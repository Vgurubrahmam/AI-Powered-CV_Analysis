import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { toast } from 'sonner'
import { Loader2, ArrowLeft, Wand2, AlertCircle, CheckCircle, XCircle, TrendingUp } from 'lucide-react'
import { motion } from 'framer-motion'
import { analysisApi } from '@/api/analysis'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { AnalysisStatusBadge } from '@/components/features/analysis-status-badge'
import { ScoreRadarChart } from '@/components/features/score-radar-chart'
import { scoreColor, scoreLabel } from '@/lib/utils'
import type { FeedbackItemRead, RewriteResult } from '@/types/analysis'

export default function AnalysisDetailPage() {
  const { id } = useParams<{ id: string }>()
  const [rewriteResult, setRewriteResult] = useState<RewriteResult | null>(null)
  const [rewritingId, setRewritingId] = useState<string | null>(null)

  const { data: analysis, isLoading: aLoading } = useQuery({
    queryKey: ['analysis', id],
    queryFn: () => analysisApi.get(id!),
    refetchInterval: (q) => {
      const s = q.state.data?.status
      return s && !['DONE', 'FAILED'].includes(s) ? 3000 : false
    },
    enabled: !!id,
  })

  const { data: score, isLoading: sLoading } = useQuery({
    queryKey: ['analysis', id, 'score'],
    queryFn: () => analysisApi.getScore(id!),
    enabled: analysis?.status === 'DONE',
  })

  const { data: feedback, isLoading: fLoading } = useQuery({
    queryKey: ['analysis', id, 'feedback'],
    queryFn: () => analysisApi.getFeedback(id!),
    enabled: analysis?.status === 'DONE',
  })

  const rewriteMutation = useMutation({
    mutationFn: (feedbackId: string) =>
      analysisApi.rewrite(id!, { feedback_item_id: feedbackId }),
    onMutate: (fid) => setRewritingId(fid),
    onSuccess: (result) => { setRewriteResult(result); setRewritingId(null) },
    onError: () => { toast.error('Rewrite failed'); setRewritingId(null) },
  })

  if (aLoading) {
    return (
      <div className="space-y-6 max-w-4xl">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="flex flex-col items-center gap-3 py-20">
        <AlertCircle className="h-10 w-10 text-muted-foreground" />
        <p className="text-sm text-muted-foreground">Analysis not found</p>
        <Button variant="outline" asChild><Link to="/analysis">← Back</Link></Button>
      </div>
    )
  }

  const isDone = analysis.status === 'DONE'

  const stageProgress: Record<string, number> = {
    QUEUED: 10, PARSING: 30, MATCHING: 50, SCORING: 70, FEEDBACK: 85, DONE: 100, PARTIAL: 90, FAILED: 0,
  }

  return (
    <div className="space-y-6 max-w-4xl">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" asChild>
          <Link to="/analysis" aria-label="Back to analyses"><ArrowLeft className="h-4 w-4" /></Link>
        </Button>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h1 className="text-xl font-semibold font-mono">#{analysis.id.slice(0, 8)}</h1>
            <AnalysisStatusBadge status={analysis.status} />
          </div>
          <p className="text-sm text-muted-foreground mt-0.5">Resume vs Job analysis</p>
        </div>
        {isDone && analysis.score_composite != null && (
          <div className="text-right">
            <p className={`text-4xl font-bold ${scoreColor(analysis.score_composite)}`}>
              {Math.round(analysis.score_composite)}%
            </p>
            <p className="text-xs text-muted-foreground">{scoreLabel(analysis.score_composite)} match</p>
          </div>
        )}
      </div>

      {/* In-progress */}
      {!isDone && analysis.status !== 'FAILED' && (
        <Card>
          <CardContent className="pt-6 pb-6 flex flex-col items-center gap-4 text-center">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <div>
              <p className="font-medium">Analysis in progress</p>
              <p className="text-sm text-muted-foreground mt-1">
                Auto-refreshing every 3 seconds. Current stage: <span className="text-primary font-medium">{analysis.status}</span>
              </p>
            </div>
            <Progress value={stageProgress[analysis.status] ?? 0} className="w-full max-w-xs" />
          </CardContent>
        </Card>
      )}

      {/* Failed */}
      {analysis.status === 'FAILED' && (
        <Card className="border-destructive/40">
          <CardContent className="pt-5 flex items-center gap-3">
            <XCircle className="h-5 w-5 text-destructive shrink-0" />
            <p className="text-sm">Analysis failed. Please create a new analysis.</p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {isDone && score && !sLoading && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.4 }}>
          <Tabs defaultValue="overview">
            <TabsList className="mb-2">
              <TabsTrigger value="overview">Overview</TabsTrigger>
              <TabsTrigger value="feedback">
                Feedback {feedback?.length ? `(${feedback.length})` : ''}
              </TabsTrigger>
              <TabsTrigger value="skills">Skills</TabsTrigger>
            </TabsList>

            <TabsContent value="overview">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Score Breakdown
                    </CardTitle>
                  </CardHeader>
                  <CardContent><ScoreRadarChart result={score} /></CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                      Sub-scores
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-5">
                    {([
                      ['Keyword Match', score.score_breakdown?.keyword],
                      ['Semantic Match', score.score_breakdown?.semantic],
                      ['Experience', score.score_breakdown?.experience],
                      ['Impact', score.score_breakdown?.impact],
                    ] as [string, number | undefined][]).map(([label, val]) =>
                      val != null ? (
                        <div key={label}>
                          <div className="flex justify-between text-sm mb-1.5">
                            <span className="text-muted-foreground">{label}</span>
                            <span className={`font-semibold ${scoreColor(val)}`}>{Math.round(val)}%</span>
                          </div>
                          <Progress value={val} />
                        </div>
                      ) : null
                    )}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>

            <TabsContent value="feedback">
              {fLoading ? (
                <div className="space-y-3">
                  {[1, 2, 3].map(i => <Skeleton key={i} className="h-24 w-full rounded-xl" />)}
                </div>
              ) : !feedback?.length ? (
                <div className="flex flex-col items-center gap-3 py-12 text-center">
                  <CheckCircle className="h-10 w-10 text-emerald-500" />
                  <p className="text-sm text-muted-foreground">No feedback — excellent match!</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {feedback.map(item => (
                    <FeedbackCard
                      key={item.id}
                      item={item}
                      isRewriting={rewritingId === item.id}
                      onRewrite={() => rewriteMutation.mutate(item.id)}
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent value="skills">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2 text-emerald-500">
                      <CheckCircle className="h-4 w-4" /> Matched Skills
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {score.keyword_detail?.matched_required?.length ? (
                      <div className="flex flex-wrap gap-1.5">
                        {score.keyword_detail.matched_required.map(s => <Badge key={s} variant="success">{s}</Badge>)}
                      </div>
                    ) : <p className="text-sm text-muted-foreground">None found</p>}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm flex items-center gap-2 text-destructive">
                      <XCircle className="h-4 w-4" /> Missing Skills
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {score.keyword_detail?.missing_required?.length ? (
                      <div className="flex flex-wrap gap-1.5">
                        {score.keyword_detail.missing_required.map(s => <Badge key={s} variant="destructive">{s}</Badge>)}
                      </div>
                    ) : <p className="text-sm text-muted-foreground">None — great coverage!</p>}
                  </CardContent>
                </Card>
              </div>
            </TabsContent>
          </Tabs>
        </motion.div>
      )}

      {/* Rewrite modal */}
      <Dialog open={!!rewriteResult} onOpenChange={() => setRewriteResult(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>AI Rewrite Preview</DialogTitle>
            <DialogDescription>
              {rewriteResult?.hallucination_check_passed
                ? '✓ Hallucination check passed — safe to use'
                : '⚠ Hallucination check flagged — review carefully'}
            </DialogDescription>
          </DialogHeader>
          {rewriteResult && (
            <div className="space-y-4">
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase mb-2">Original</p>
                <p className="text-sm bg-muted rounded-lg p-3 leading-relaxed">{rewriteResult.original_text}</p>
              </div>
              <div>
                <p className="text-xs font-semibold text-emerald-500 uppercase mb-2">Rewritten</p>
                <p className="text-sm bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3 leading-relaxed">
                  {rewriteResult.rewritten_text}
                </p>
              </div>
              {rewriteResult.warning && (
                <p className="text-xs text-amber-500 flex items-center gap-1.5">
                  <AlertCircle className="h-3.5 w-3.5" />{rewriteResult.warning}
                </p>
              )}
              {rewriteResult.flagged_entities.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {rewriteResult.flagged_entities.map(e => <Badge key={e} variant="warning">{e}</Badge>)}
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  )
}

function FeedbackCard({
  item, isRewriting, onRewrite,
}: { item: FeedbackItemRead; isRewriting: boolean; onRewrite: () => void }) {
  const priorityMap = { critical: 'destructive', high: 'destructive', medium: 'warning', low: 'info' } as const
  return (
    <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}>
      <Card>
        <CardContent className="pt-5 pb-4">
          <div className="flex items-center gap-2 mb-2">
            <Badge variant={priorityMap[item.severity]}>{item.severity}</Badge>
            <span className="text-xs text-muted-foreground capitalize">{item.category}</span>
            {item.score_delta != null && (
              <span className="ml-auto text-xs text-emerald-500 flex items-center gap-1">
                <TrendingUp className="h-3 w-3" />+{item.score_delta.toFixed(1)} pts
              </span>
            )}
          </div>
          {item.title && <p className="text-sm font-medium mb-1">{item.title}</p>}
          <p className="text-sm">{item.description}</p>
          {item.original_text && (
            <p className="text-xs text-muted-foreground mt-1.5 line-clamp-2 italic">"{item.original_text}"</p>
          )}
          {item.original_text && (
            <Button variant="outline" size="sm" className="mt-3" onClick={onRewrite} disabled={isRewriting}>
              {isRewriting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}
              Rewrite with AI
            </Button>
          )}
        </CardContent>
      </Card>
    </motion.div>
  )
}
