import { Suspense } from 'react'
import { RouterProvider } from 'react-router'
import { router } from './routes'

export default function App() {
  return (
    <Suspense fallback={<AppLoading />}>
      <RouterProvider router={router} />
    </Suspense>
  )
}

function AppLoading() {
  return (
    <div className="flex h-screen items-center justify-center bg-background text-sm text-muted-foreground">
      加载中...
    </div>
  )
}
