import './Inference.css'
import { Ask } from './inference/Ask'
import { Coaching } from './inference/Coaching'
import { Enrichment } from './inference/Enrichment'

export function Inference() {
  return (
    <>
      <Enrichment />
      <Coaching />
      <Ask />
    </>
  )
}
