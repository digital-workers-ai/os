import { Banner } from '@/components/ui/banner'
import { buttonVariants } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import { cn } from '@/lib/utils'

const loginHref = () => `/api/auth/login?next=${encodeURIComponent(window.location.href)}`

const denied = () => new URLSearchParams(window.location.search).get('login') === 'denied'

export function Login() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-surface px-4">
      <Card className="w-full max-w-sm space-y-4" data-testid="login">
        <div>
          <h1 className="text-lg font-semibold text-ink">DW-OS</h1>
          <p className="mt-1 text-sm text-muted">Sign in to open the console</p>
        </div>
        <a href={loginHref()} className={cn(buttonVariants(), 'w-full')} data-testid="login-google">
          Sign in with Google
        </a>
        {denied() && (
          <Banner tone="err" testId="login-denied">
            That account is not allowed. Ask whoever runs this DW-OS to add it to AUTH_ALLOWED_EMAILS.
          </Banner>
        )}
        <p className="text-xs text-muted">Access is limited to the accounts in AUTH_ALLOWED_EMAILS.</p>
      </Card>
    </div>
  )
}
