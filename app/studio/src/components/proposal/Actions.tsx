import { Button } from '@/components/ui/button'

export function Actions({
  approveLabel,
  approveDisabled,
  pending,
  onApprove,
  onEditApprove,
  onReject,
  onRedo,
}: {
  approveLabel: string
  approveDisabled: boolean
  pending: boolean
  onApprove: () => void
  onEditApprove: () => void
  onReject: () => void
  onRedo: () => void
}) {
  return (
    <div className="flex flex-wrap gap-2 border-t border-line pt-4" data-testid="proposal-actions">
      <Button disabled={approveDisabled || pending} onClick={onApprove} data-testid="approve-btn">
        {approveLabel}
      </Button>
      <Button disabled={pending} onClick={onEditApprove} data-testid="edit-approve-btn">
        Edit → approve
      </Button>
      <Button disabled={pending} onClick={onReject} data-testid="reject-btn">
        Reject
      </Button>
      <Button disabled={pending} onClick={onRedo} data-testid="redo-btn">
        Redo with note
      </Button>
    </div>
  )
}
