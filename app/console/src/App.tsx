import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { PageHeader } from '@/components/PageHeader'
import { ROUTES } from '@/routes'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          {ROUTES.map(({ to, title, tabs, view: View }) => {
            const page = (
              <>
                <PageHeader title={title} />
                <View />
              </>
            )
            return tabs ? (
              <Route key={to} path={to}>
                <Route index element={<Navigate to={tabs[0].value} replace />} />
                <Route path=":tab" element={page} />
              </Route>
            ) : (
              <Route key={to} path={to} element={page} />
            )
          })}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
