import type { ControlProps } from './context'
import { DateField } from './DateField'
import { ListField } from './ListField'
import { LookupField } from './LookupField'
import { ManyOfField } from './ManyOfField'
import { NumberField } from './NumberField'
import { OneOfField } from './OneOfField'
import { PhotoField } from './PhotoField'
import { ScreenField } from './ScreenField'
import { TextField } from './TextField'

export function Control(props: ControlProps) {
  switch (props.field.type) {
    case 'number':
    case 'money':
      return <NumberField {...props} />
    case 'date':
      return <DateField {...props} />
    case 'one_of':
      return <OneOfField {...props} />
    case 'many_of':
      return <ManyOfField {...props} />
    case 'lookup':
      return <LookupField {...props} />
    case 'photo':
      return <PhotoField {...props} />
    case 'list':
      return <ListField {...props} />
    case 'screen':
      return <ScreenField {...props} />
    default:
      return <TextField {...props} />
  }
}
