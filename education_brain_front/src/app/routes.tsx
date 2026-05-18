import { createBrowserRouter } from 'react-router'
import { Layout } from './components/layout'
import { ChatPage } from './pages/chat-page'
import { CoursesPage } from './pages/courses-page'
import { QuestionsPage } from './pages/questions-page'
import { DocumentsPage } from './pages/documents-page'
import { IngestPage } from './pages/ingest-page'

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
