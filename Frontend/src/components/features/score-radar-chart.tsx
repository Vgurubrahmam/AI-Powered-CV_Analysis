import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar,
  ResponsiveContainer, Tooltip,
} from 'recharts'
import type { AnalysisResultRead } from '@/types/analysis'

interface Props {
  result: AnalysisResultRead
}

export function ScoreRadarChart({ result }: Props) {
  const bd = result.score_breakdown
  const data = [
    { subject: 'Keyword', value: Math.round(bd?.keyword ?? 0) },
    { subject: 'Semantic', value: Math.round(bd?.semantic ?? 0) },
    { subject: 'Experience', value: Math.round(bd?.experience ?? 0) },
    { subject: 'Impact', value: Math.round(bd?.impact ?? 0) },
  ]

  return (
    <ResponsiveContainer width="100%" height={260}>
      <RadarChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
        <PolarGrid stroke="hsl(var(--border))" />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: 'hsl(var(--muted-foreground))', fontSize: 12 }}
        />
        <Radar
          name="Score"
          dataKey="value"
          stroke="hsl(var(--primary))"
          fill="hsl(var(--primary))"
          fillOpacity={0.25}
          strokeWidth={2}
        />
        <Tooltip
          contentStyle={{
            backgroundColor: 'hsl(var(--card))',
            border: '1px solid hsl(var(--border))',
            borderRadius: '8px',
            fontSize: '12px',
            color: 'hsl(var(--foreground))',
          }}
          formatter={(v) => [`${Number(v)}%`, 'Score']}
        />
      </RadarChart>
    </ResponsiveContainer>
  )
}
