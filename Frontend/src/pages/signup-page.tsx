import { useState, useMemo } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { BrainCircuit, Loader2, Eye, EyeOff, CheckCircle2, XCircle, ShieldCheck, Sparkles, Users, Zap } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'sonner'
import { useAuth } from '@/contexts/auth-context'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { ApiError } from '@/lib/query-client'

// ─── Password strength rules ─────────────────────────────────────────────────

interface PasswordRule {
  label: string
  test: (v: string) => boolean
}

const PASSWORD_RULES: PasswordRule[] = [
  { label: 'At least 8 characters', test: (v) => v.length >= 8 },
  { label: 'One uppercase letter', test: (v) => /[A-Z]/.test(v) },
  { label: 'One digit (0–9)', test: (v) => /\d/.test(v) },
]

function getStrengthLevel(pw: string): { level: number; label: string; color: string } {
  const passed = PASSWORD_RULES.filter((r) => r.test(pw)).length
  if (pw.length === 0) return { level: 0, label: '', color: '' }
  if (passed === 1) return { level: 1, label: 'Weak', color: 'bg-red-500' }
  if (passed === 2) return { level: 2, label: 'Fair', color: 'bg-amber-400' }
  return { level: 3, label: 'Strong', color: 'bg-emerald-500' }
}

// ─── Zod schema ───────────────────────────────────────────────────────────────

const schema = z
  .object({
    email: z.string().email('Enter a valid email address'),
    password: z
      .string()
      .min(8, 'Password must be at least 8 characters')
      .regex(/[A-Z]/, 'Password must contain at least one uppercase letter')
      .regex(/\d/, 'Password must contain at least one digit'),
    confirmPassword: z.string().min(1, 'Please confirm your password'),
  })
  .refine((d) => d.password === d.confirmPassword, {
    message: "Passwords don't match",
    path: ['confirmPassword'],
  })

type FormData = z.infer<typeof schema>

// ─── Branding stats ───────────────────────────────────────────────────────────

const STATS = [
  { icon: Users, value: '10k+', label: 'Professionals' },
  { icon: Zap, value: '3s', label: 'Avg. analysis' },
  { icon: ShieldCheck, value: '99.9%', label: 'Uptime SLA' },
]

const FEATURES = [
  'AI-powered resume scoring against job descriptions',
  'ATS keyword optimisation & gap analysis',
  'Real-time feedback with actionable insights',
  'Enterprise-grade security & data privacy',
]

// ─── Component ────────────────────────────────────────────────────────────────

export default function SignupPage() {
  const { signup } = useAuth()
  const navigate = useNavigate()
  const [showPw, setShowPw] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema), mode: 'onChange' })

  const passwordValue = watch('password', '')
  const strength = useMemo(() => getStrengthLevel(passwordValue), [passwordValue])

  const onSubmit = async (data: FormData) => {
    try {
      await signup(data.email, data.password)
      toast.success('Account created! Welcome aboard 🎉')
      navigate('/dashboard', { replace: true })
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : 'Registration failed. Please try again.'
      toast.error(msg)
    }
  }

  return (
    <div className="min-h-screen bg-background flex">
      {/* ── Left branding panel ── */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 p-12 gradient-primary relative overflow-hidden">
        {/* Decorative blobs */}
        <div className="absolute -top-20 -right-20 w-80 h-80 rounded-full bg-white/5 blur-3xl pointer-events-none" />
        <div className="absolute -bottom-20 -left-20 w-96 h-96 rounded-full bg-white/5 blur-3xl pointer-events-none" />

        {/* Logo */}
        <div className="flex items-center gap-3 relative z-10">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/20">
            <BrainCircuit className="h-5 w-5 text-white" />
          </div>
          <span className="text-white text-lg font-bold">ResumeAI</span>
        </div>

        {/* Headline */}
        <div className="relative z-10 space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Sparkles className="h-4 w-4 text-white/70" />
              <span className="text-white/70 text-sm font-medium uppercase tracking-widest">
                Join for free
              </span>
            </div>
            <h1 className="text-white text-4xl font-bold leading-tight">
              Land your dream job <br />faster with AI.
            </h1>
            <p className="text-white/70 mt-3 text-base leading-relaxed">
              Analyse, optimise, and tailor your resume to every job description in seconds.
            </p>
          </div>

          {/* Feature list */}
          <ul className="space-y-3">
            {FEATURES.map((f) => (
              <li key={f} className="flex items-start gap-3 text-white/80 text-sm">
                <CheckCircle2 className="h-4 w-4 text-white/60 mt-0.5 shrink-0" />
                {f}
              </li>
            ))}
          </ul>
        </div>

        {/* Stats */}
        <div className="flex gap-8 relative z-10">
          {STATS.map(({ icon: Icon, value, label }) => (
            <div key={label} className="text-white/80">
              <div className="flex items-center gap-1.5 mb-0.5">
                <Icon className="h-4 w-4 text-white/50" />
                <p className="text-2xl font-bold text-white leading-none">{value}</p>
              </div>
              <p className="text-xs">{label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Right form panel ── */}
      <div className="flex-1 flex items-center justify-center p-8 overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="w-full max-w-md"
        >
          {/* Mobile logo */}
          <div className="flex items-center gap-2 mb-8 lg:hidden">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg gradient-primary">
              <BrainCircuit className="h-4 w-4 text-white" />
            </div>
            <span className="font-bold">ResumeAI</span>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-xl">Create your account</CardTitle>
              <CardDescription>
                Get started for free — no credit card required.
              </CardDescription>
            </CardHeader>

            <CardContent>
              <form
                id="signup-form"
                onSubmit={handleSubmit(onSubmit)}
                className="space-y-5"
                noValidate
              >
                {/* Email */}
                <div className="space-y-2">
                  <Label htmlFor="signup-email">Email address</Label>
                  <Input
                    id="signup-email"
                    type="email"
                    placeholder="you@company.com"
                    autoComplete="email"
                    {...register('email')}
                  />
                  {errors.email && (
                    <p className="text-xs text-destructive">{errors.email.message}</p>
                  )}
                </div>

                {/* Password */}
                <div className="space-y-2">
                  <Label htmlFor="signup-password">Password</Label>
                  <div className="relative">
                    <Input
                      id="signup-password"
                      type={showPw ? 'text' : 'password'}
                      placeholder="Min. 8 characters"
                      autoComplete="new-password"
                      className="pr-10"
                      {...register('password')}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPw((p) => !p)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={showPw ? 'Hide password' : 'Show password'}
                    >
                      {showPw ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>

                  {/* Strength bar */}
                  <AnimatePresence>
                    {passwordValue.length > 0 && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="space-y-2 overflow-hidden"
                      >
                        {/* Bar */}
                        <div className="flex gap-1 h-1.5">
                          {[1, 2, 3].map((i) => (
                            <div
                              key={i}
                              className={`flex-1 rounded-full transition-all duration-300 ${
                                i <= strength.level
                                  ? strength.color
                                  : 'bg-muted'
                              }`}
                            />
                          ))}
                        </div>
                        {strength.label && (
                          <p className="text-xs text-muted-foreground">
                            Strength:{' '}
                            <span
                              className={
                                strength.level === 3
                                  ? 'text-emerald-500 font-medium'
                                  : strength.level === 2
                                  ? 'text-amber-500 font-medium'
                                  : 'text-red-500 font-medium'
                              }
                            >
                              {strength.label}
                            </span>
                          </p>
                        )}

                        {/* Rules checklist */}
                        <ul className="space-y-1">
                          {PASSWORD_RULES.map((rule) => {
                            const ok = rule.test(passwordValue)
                            return (
                              <li
                                key={rule.label}
                                className="flex items-center gap-1.5 text-xs"
                              >
                                {ok ? (
                                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                                ) : (
                                  <XCircle className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                                )}
                                <span
                                  className={
                                    ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-muted-foreground'
                                  }
                                >
                                  {rule.label}
                                </span>
                              </li>
                            )
                          })}
                        </ul>
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {errors.password && (
                    <p className="text-xs text-destructive">{errors.password.message}</p>
                  )}
                </div>

                {/* Confirm password */}
                <div className="space-y-2">
                  <Label htmlFor="signup-confirm-password">Confirm password</Label>
                  <div className="relative">
                    <Input
                      id="signup-confirm-password"
                      type={showConfirm ? 'text' : 'password'}
                      placeholder="Re-enter your password"
                      autoComplete="new-password"
                      className="pr-10"
                      {...register('confirmPassword')}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((p) => !p)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                      aria-label={showConfirm ? 'Hide confirm password' : 'Show confirm password'}
                    >
                      {showConfirm ? (
                        <EyeOff className="h-4 w-4" />
                      ) : (
                        <Eye className="h-4 w-4" />
                      )}
                    </button>
                  </div>
                  {errors.confirmPassword && (
                    <p className="text-xs text-destructive">
                      {errors.confirmPassword.message}
                    </p>
                  )}
                </div>

                {/* Submit */}
                <Button
                  id="signup-submit-btn"
                  type="submit"
                  className="w-full"
                  disabled={isSubmitting}
                >
                  {isSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                  {isSubmitting ? 'Creating account…' : 'Create free account'}
                </Button>
              </form>

              {/* Login link */}
              <p className="mt-6 text-center text-sm text-muted-foreground">
                Already have an account?{' '}
                <Link
                  to="/login"
                  className="font-medium text-foreground underline-offset-4 hover:underline transition-colors"
                >
                  Sign in
                </Link>
              </p>

              {/* ToS note */}
              <p className="mt-3 text-center text-xs text-muted-foreground">
                By signing up you agree to our{' '}
                <span className="underline cursor-pointer hover:text-foreground transition-colors">
                  Terms of Service
                </span>{' '}
                and{' '}
                <span className="underline cursor-pointer hover:text-foreground transition-colors">
                  Privacy Policy
                </span>
                .
              </p>
            </CardContent>
          </Card>
        </motion.div>
      </div>
    </div>
  )
}
