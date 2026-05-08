export type JDParseStatus = 'PENDING' | 'SUCCESS' | 'PARTIAL' | 'FAILED'

export interface JDCreate {
  raw_text: string
  title?: string
  company?: string
}

export interface JDRead {
  id: string
  user_id: string | null
  title: string | null
  company: string | null
  parse_status: JDParseStatus
  created_at: string
}

export interface ParsedJDData {
  role_title?: string
  seniority?: string
  required_skills: string[]
  preferred_skills: string[]
  years_experience_required?: {
    min?: number
    max?: number
    flexible?: boolean
  }
  education_required?: {
    level?: string
    field?: string
    required?: boolean
  }
  responsibilities: string[]
  must_have_flags: string[]
  jd_quality_warnings: string[]
  aspirational_requirements: string[]
}

export interface ParsedJDRead extends JDRead {
  parsed_data: ParsedJDData | null
  raw_text: string
}
