import { lazy } from 'react'
import { Navigate, createBrowserRouter } from 'react-router'
import { Layout } from './components/layout'

const ChatPage = lazy(() => import('./pages/chat-page').then((module) => ({ default: module.ChatPage })))

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      { index: true, Component: ChatPage },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
])
