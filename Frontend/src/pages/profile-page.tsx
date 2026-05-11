import { useState } from 'react'
import { useMutation, useQuery } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { toast } from 'sonner'
import { Loader2, Mail, Shield } from 'lucide-react'
import { usersApi } from '@/api/users'
import { useAuth } from '@/contexts/auth-context'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Separator } from '@/components/ui/separator'
import { formatDate } from '@/lib/utils'

const profileSchema = z.object({
  email: z.string().email('Enter a valid email').optional().or(z.literal('')),
  password: z.string().min(8, 'Password must be at least 8 characters').optional().or(z.literal('')),
})
type FormData = z.infer<typeof profileSchema>

export default function ProfilePage() {
  const { user } = useAuth()
  const [saved, setSaved] = useState(false)

  const { data: profile, isLoading } = useQuery({
    queryKey: ['users', 'me'],
    queryFn: () => usersApi.getMe(),
  })

  const { register, handleSubmit, reset, formState: { errors, isSubmitting } } = useForm<FormData>({
    resolver: zodResolver(profileSchema),
  })

  const updateMutation = useMutation({
    mutationFn: (data: FormData) =>
      usersApi.updateMe({
        email: data.email || undefined,
        password: data.password || undefined,
      }),
    onSuccess: () => {
      toast.success('Profile updated successfully')
      setSaved(true)
      reset()
      setTimeout(() => setSaved(false), 3000)
    },
    onError: () => toast.error('Failed to update profile'),
  })

  const initials = (profile?.email ?? user?.email ?? 'U').slice(0, 2).toUpperCase()

  return (
    <div className="space-y-6 max-w-2xl">
      {/* Profile summary */}
      <Card>
        <CardContent className="pt-6">
          {isLoading ? (
            <div className="flex items-center gap-4">
              <Skeleton className="h-16 w-16 rounded-full" />
              <div className="space-y-2 flex-1">
                <Skeleton className="h-5 w-48" />
                <Skeleton className="h-4 w-32" />
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center rounded-full gradient-primary text-white text-xl font-bold">
                {initials}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate">{profile?.email ?? '—'}</p>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="secondary" className="capitalize gap-1">
                    <Shield className="h-3 w-3" />
                    {profile?.role ?? 'user'}
                  </Badge>
                  <Badge variant={profile?.is_active ? 'success' : 'destructive'}>
                    {profile?.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                </div>
              </div>
              <div className="text-right text-xs text-muted-foreground">
                <p>Member since</p>
                <p className="font-medium text-foreground">{profile?.created_at ? formatDate(profile.created_at) : '—'}</p>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Edit form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Update Profile</CardTitle>
          <CardDescription>Change your email or password. Leave fields blank to keep current values.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(d => updateMutation.mutate(d))} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="profile-email" className="flex items-center gap-1.5">
                <Mail className="h-3.5 w-3.5" /> New Email
              </Label>
              <Input
                id="profile-email"
                type="email"
                placeholder={profile?.email ?? 'you@company.com'}
                {...register('email')}
              />
              {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
            </div>
            <Separator />
            <div className="space-y-2">
              <Label htmlFor="profile-password" className="flex items-center gap-1.5">
                <Shield className="h-3.5 w-3.5" /> New Password
              </Label>
              <Input
                id="profile-password"
                type="password"
                placeholder="Min. 8 characters"
                {...register('password')}
              />
              {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button type="button" variant="outline" onClick={() => reset()}>Reset</Button>
              <Button type="submit" disabled={isSubmitting || updateMutation.isPending}>
                {updateMutation.isPending && <Loader2 className="h-4 w-4 animate-spin" />}
                {saved ? 'Saved!' : 'Save Changes'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
