export type ParseStatus = 'PENDING' | 'SUCCESS' | 'PARTIAL' | 'FAILED'

export interface ResumeRead {
  id: string
  user_id: string
  file_name: string
  file_type: string
  file_size_bytes: number | null
  parse_status: ParseStatus
  parse_confidence: number | null
  version: number
  language: string
  created_at: string
}

export interface ResumeUploadResponse {
  resume_id: string
  status: ParseStatus
  message: string
}

// ── Parsed resume sub-types ──────────────────────────────────────────────────

export interface ParsedContact {
  name?: string
  email?: string
  phone?: string
  linkedin?: string
  github?: string
  location?: string
  website?: string
}

export interface ParsedExperienceItem {
  company?: string
  title?: string
  start_date?: string
  end_date?: string
  duration_months?: number
  bullets: string[]
  location?: string
}

export interface ParsedEducationItem {
  institution?: string
  degree?: string
  field?: string
  start_date?: string
  end_date?: string
  gpa?: number
}

export interface ParsedResumeData {
  contact: ParsedContact
  summary?: string
  experience: ParsedExperienceItem[]
  education: ParsedEducationItem[]
  skills: string[]
  certifications: string[]
  projects: string[]
  languages: string[]
  sections_detected: string[]
  total_yoe?: number
}

export interface ParsedResumeRead extends ResumeRead {
  parsed_data: ParsedResumeData | null
  raw_text: string | null
}
