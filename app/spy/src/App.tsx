import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { getVisibility } from '@/api'
import { Layout } from '@/components/Layout'
import { FIRST } from '@/lib/pages'
import { DEFAULT_RANGE, type Range } from '@/lib/range'
import { Ads } from '@/views/Ads'
import { Competitors } from '@/views/Competitors'
import { Overview } from '@/views/Overview'
import { Posts } from '@/views/Posts'
import { Visibility } from '@/views/Visibility'

export default function App() {
  const today = useQuery({
    queryKey: ['today'],
    queryFn: () => getVisibility(),
    select: (r) => r.as_of.slice(0, 10),
    staleTime: Infinity,
  })
  const [range, setRange] = useState<Range>(DEFAULT_RANGE)
  const ranged = { today: today.data ?? null, todayError: today.error, range }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout today={ranged.today} range={range} onRange={setRange} />}>
          <Route index element={<Navigate to={`/${FIRST}`} replace />} />
          <Route path="overview" element={<Overview {...ranged} />} />
          <Route path="visibility/:engine?" element={<Visibility {...ranged} />} />
          <Route path="ads/:platform?" element={<Ads {...ranged} />} />
          <Route path="posts" element={<Posts {...ranged} />} />
          <Route path="competitors" element={<Competitors />} />
          <Route path="*" element={<Navigate to={`/${FIRST}`} replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
