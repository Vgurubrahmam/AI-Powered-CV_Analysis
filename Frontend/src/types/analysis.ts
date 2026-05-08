export type AnalysisStatus = 'QUEUED' | 'PARSING' | 'MATCHING' | 'SCORING' | 'FEEDBACK' | 'DONE' | 'FAILED' | 'PARTIAL'
export type FeedbackSeverity = 'critical' | 'high' | 'medium' | 'low'
export type FeedbackCategory = 'keyword' | 'semantic' | 'impact' | 'ats' | 'education' | 'experience' | 'formatting'

export interface AnalysisRequest {
  resume_id: string
  job_id: string
}

export interface AnalysisCreateResponse {
  analysis_id: string
  status: AnalysisStatus
  message: string
}

export interface AnalysisRead {
  id: string
  resume_id: string
  job_id: string
  status: AnalysisStatus
  score_composite: number | null
  confidence: number | null
  percentile: number | null
  created_at: string
  completed_at: string | null
  celery_task_id: string | null
}

export interface ScoreBreakdown {
  keyword?: number
  semantic?: number
  skill_depth?: number
  experience?: number
  impact?: number
  education?: number
}

export interface AnalysisResultRead extends AnalysisRead {
  score_breakdown: ScoreBreakdown | null
  confidence_interval?: {
    lower: number
    upper: number
    confidence: number
  }
  keyword_detail?: {
    matched_required: string[]
    missing_required: string[]
    matched_preferred: string[]
    match_rate: number
  }
  semantic_detail?: {
    per_requirement_scores: Record<string, number>
    mean_score: number
    strong_matches: string[]
    weak_matches: string[]
  }
  experience_detail?: {
    total_yoe?: number
    required_yoe?: number
    seniority_inferred?: string
    seniority_required?: string
    career_progression_score?: number
  }
  ats_warnings: string[]
  pipeline_meta: Record<string, unknown> | null
}

export interface FeedbackItemRead {
  id: string
  analysis_id: string
  category: FeedbackCategory
  severity: FeedbackSeverity
  title: string
  description: string
  original_text: string | null
  suggested_text: string | null
  score_delta: number | null
  source_section: string | null
  accepted: boolean | null
  created_at: string
}

export interface RewriteRequest {
  feedback_item_id: string
  section: string
}

export interface RewriteResult {
  feedback_item_id: string
  original_text: string
  rewritten_text: string
  hallucination_check_passed: boolean
  flagged_entities: string[]
  warning?: string
}
