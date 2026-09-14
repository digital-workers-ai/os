import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Activity } from '@/views/Activity'
import { AssetDetail } from '@/views/AssetDetail'
import { Assets } from '@/views/Assets'
import { Calendar } from '@/views/Calendar'
import { Canvas } from '@/views/Canvas'
import { Competitors } from '@/views/Competitors'
import { Context } from '@/views/Context'
import { ProposalDetail } from '@/views/ProposalDetail'
import { Proposals } from '@/views/Proposals'
import { SwipeItemView } from '@/views/SwipeItem'
import { Today } from '@/views/Today'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Today />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="proposals" element={<Proposals />} />
          <Route path="proposals/:seq" element={<ProposalDetail />} />
          <Route path="canvas" element={<Canvas />} />
          <Route path="competitors" element={<Navigate to="/competitors/swipe" replace />} />
          <Route path="competitors/swipe/:id" element={<SwipeItemView />} />
          <Route path="competitors/:tab" element={<Competitors />} />
          <Route path="assets" element={<Assets />} />
          <Route path="assets/:seq" element={<AssetDetail />} />
          <Route path="context" element={<Navigate to="/context/brand" replace />} />
          <Route path="context/:tab" element={<Context />} />
          <Route path="activity" element={<Activity />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
