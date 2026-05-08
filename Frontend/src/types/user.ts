export interface UserRead {
  id: string
  email: string
  role: string
  plan_tier: string
  is_active: boolean
  created_at: string
}

export interface UserUpdate {
  email?: string
  password?: string
}
