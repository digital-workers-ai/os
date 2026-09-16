import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { AssetDetail } from '@/views/AssetDetail'
import { Assets } from '@/views/Assets'
import { Calendar } from '@/views/Calendar'
import { Canvas } from '@/views/Canvas'
import { Create } from '@/views/Create'
import { Today } from '@/views/Today'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Canvas />} />
          <Route path="create" element={<Create />} />
          <Route path="create/:seq" element={<Create />} />
          <Route path="assets" element={<Assets />} />
          <Route path="assets/:seq" element={<AssetDetail />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="today" element={<Today />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
