import { lazy, Suspense, type ComponentType } from 'react'
import { fileUrl, type RecordFile, type Sent } from '@/api'
import { Loading } from '@/components/ui/loading'
import { stem } from '@/lib/files'
import { useForm, type ControlProps } from './context'

export interface ScreenProps {
  name: string
  value: unknown
  onChange: (value: unknown) => void
  src: string | null
  upload: (file: Sent) => Promise<RecordFile>
  disabled?: boolean
}

const SCREENS = import.meta.glob<{ default: ComponentType<ScreenProps> }>('../../apps/*/screen.tsx')

const screens = Object.fromEntries(Object.entries(SCREENS).map(([path, load]) => [path.split('/').at(-2), lazy(load)]))

export function ScreenField({ field, value, onChange, testId, disabled }: ControlProps) {
  const { app, record, files, upload } = useForm()
  const Screen = screens[app.name]
  const stored = files.find((file) => file.path === value) ?? files.find((file) => stem(file.path) === field.name)
  return (
    <div data-testid={testId}>
      {Screen ? (
        <Suspense fallback={<Loading />}>
          <Screen
            name={field.name}
            value={value}
            onChange={onChange}
            src={record && stored ? fileUrl(record, stored.path) : null}
            upload={upload}
            disabled={disabled}
          />
        </Suspense>
      ) : (
        <p className="text-sm text-err">No screen at app/custom/src/apps/{app.name}/screen.tsx</p>
      )}
    </div>
  )
}
