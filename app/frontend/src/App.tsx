import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { PageHeader } from '@/components/PageHeader'
import { ROUTES } from '@/routes'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {ROUTES.map(({ to, title, view: View }) => (
            <Route
              key={to}
              path={to}
              element={
                <>
                  <PageHeader title={title} />
                  <View />
                </>
              }
            />
          ))}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
