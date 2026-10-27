import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Home } from '@/views/Home'
import { NewRecord } from '@/views/NewRecord'
import { RecordView } from '@/views/Record'
import { Records } from '@/views/Records'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Home />} />
          <Route path="apps/:app/new" element={<NewRecord />} />
          <Route path="apps/:app" element={<Records />} />
          <Route path="records/:id" element={<RecordView />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
