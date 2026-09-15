import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { HOME } from '@/tabs'
import { Answers } from '@/views/Answers'
import { GoogleAds } from '@/views/GoogleAds'
import { LinkedIn } from '@/views/LinkedIn'
import { MetaAds } from '@/views/MetaAds'
import { Pages } from '@/views/Pages'
import { Search } from '@/views/Search'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to={HOME} replace />} />
          <Route path="meta-ads" element={<MetaAds />} />
          <Route path="google-ads" element={<GoogleAds />} />
          <Route path="search" element={<Search />} />
          <Route path="answers" element={<Answers />} />
          <Route path="pages" element={<Pages />} />
          <Route path="linkedin" element={<LinkedIn />} />
          <Route path="*" element={<Navigate to={HOME} replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
