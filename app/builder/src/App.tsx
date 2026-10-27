import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { AppPage } from '@/views/AppPage'
import { Apps } from '@/views/Apps'
import { NewApp } from '@/views/NewApp'
import { ThreadPage } from '@/views/ThreadPage'
import { Threads } from '@/views/Threads'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Apps />} />
          <Route path="apps/:app" element={<AppPage />} />
          <Route path="new" element={<NewApp />} />
          <Route path="threads" element={<Threads />} />
          <Route path="threads/:id" element={<ThreadPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
