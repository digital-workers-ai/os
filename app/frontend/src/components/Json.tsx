export function Json({ value, label = 'json', open = false }: { value: unknown; label?: string; open?: boolean }) {
  return (
    <details className="json" open={open}>
      <summary>{label}</summary>
      <pre>{JSON.stringify(value, null, 2)}</pre>
    </details>
  )
}
