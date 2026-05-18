import { lazy } from 'react'
import { createBrowserRouter } from 'react-router'
import { Layout } from './components/layout'

const ChatPage = lazy(() => import('./pages/chat-page').then((module) => ({ default: module.ChatPage })))
const CoursesPage = lazy(() => import('./pages/courses-page').then((module) => ({ default: module.CoursesPage })))
const QuestionsPage = lazy(() => import('./pages/questions-page').then((module) => ({ default: module.QuestionsPage })))
const DocumentsPage = lazy(() => import('./pages/documents-page').then((module) => ({ default: module.DocumentsPage })))
const IngestPage = lazy(() => import('./pages/ingest-page').then((module) => ({ default: module.IngestPage })))

export const router = createBrowserRouter([
  {
    path: '/',
    Component: Layout,
    children: [
      { index: true, Component: ChatPage },
      { path: 'courses', Component: CoursesPage },
      { path: 'questions', Component: QuestionsPage },
      { path: 'documents', Component: DocumentsPage },
      { path: 'ingest/catalog', element: <IngestPage type="catalog" /> },
      { path: 'ingest/questions', element: <IngestPage type="questions" /> },
      { path: 'ingest/documents', element: <IngestPage type="documents" /> },
    ],
  },
])
