import { PRODUCT } from '@/brand'
import { DigitalWorkersMark } from '@/components/DigitalWorkersMark'
import { Banner } from '@/components/ui/banner'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

export function SignIn() {
  const denied = new URLSearchParams(window.location.search).get('login') === 'denied'
  const href = `/api/auth/login?next=${encodeURIComponent(window.location.href)}`
  return (
    <div className="min-h-screen bg-surface flex items-center justify-center p-6">
      <Card className="w-full max-w-sm space-y-4" data-testid="login">
        <div className="flex items-center gap-1">
          <DigitalWorkersMark size="md" phase="done" />
          <h1 className="text-[15px] font-medium text-ink leading-none">{PRODUCT}</h1>
        </div>
        <p className="text-sm text-ink">Sign in to open this page</p>
        {denied && (
          <Banner tone="err" testId="login-denied">
            That account is not allowed. Ask whoever runs this DW-OS to add it to AUTH_ALLOWED_EMAILS.
          </Banner>
        )}
        <Button asChild className="w-full">
          <a href={href} data-testid="login-google">
            Sign in with Google
          </a>
        </Button>
        <p className="text-xs text-muted">Access is limited to the accounts in AUTH_ALLOWED_EMAILS.</p>
      </Card>
    </div>
  )
}
