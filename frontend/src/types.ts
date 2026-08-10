export interface Resume {
  id: number
  filename: string
  is_primary: boolean
  uploaded_at: string
}

export interface Application {
  id: number
  dedup_key: string
  company: string
  title: string
  url: string
  ats_platform: string
  match_score: number | null
  match_reasoning: string | null
  resume_path: string | null
  status: string
  notes: string | null
  applied_at: string | null
}

export interface Run {
  id: number
  started_at: string
  finished_at: string | null
  status: string
  current_step: string | null
  postings_found: number | null
  screened_pass: number | null
  screened_reject: number | null
  applied_count: number | null
  error: string | null
}
