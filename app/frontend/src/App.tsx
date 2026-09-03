import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { PageHeader } from '@/components/PageHeader'
import { ROUTES } from '@/routes'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {ROUTES.map(({ to, title, subtitle, view: View, legacy }) => (
            <Route
              key={to}
              path={to}
              element={
                <>
                  <PageHeader title={title} subtitle={subtitle} />
                  {legacy ? (
                    <div className="legacy">
                      <View />
                    </div>
                  ) : (
                    <View />
                  )}
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
