import { memo, type ComponentPropsWithoutRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const components: ComponentPropsWithoutRef<typeof ReactMarkdown>['components'] = {
  h1: ({ children }) => (
    <h1 className="text-lg font-semibold mt-4 mb-2 first:mt-0">{children}</h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-semibold mt-3 mb-1.5 first:mt-0">{children}</h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold mt-2 mb-1 first:mt-0">{children}</h3>
  ),
  p: ({ children }) => (
    <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>
  ),
  ul: ({ children }) => (
    <ul className="mb-2 last:mb-0 pl-5 list-disc space-y-0.5">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-2 last:mb-0 pl-5 list-decimal space-y-0.5">{children}</ol>
  ),
  li: ({ children }) => (
    <li className="leading-relaxed">{children}</li>
  ),
  blockquote: ({ children }) => (
    <blockquote className="border-l-3 border-primary/30 pl-3 my-2 text-muted-foreground italic">
      {children}
    </blockquote>
  ),
  code: ({ className, children, ...props }) => {
    const isBlock = className?.includes('language-')
    if (isBlock) {
      return (
        <code className={`block bg-muted/80 rounded-md p-3 my-2 text-xs font-mono overflow-x-auto whitespace-pre ${className ?? ''}`} {...props}>
          {children}
        </code>
      )
    }
    return (
      <code className="bg-muted/80 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
        {children}
      </code>
    )
  },
  pre: ({ children }) => (
    <pre className="my-2 last:mb-0">{children}</pre>
  ),
  hr: () => (
    <hr className="my-3 border-border" />
  ),
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline underline-offset-2 hover:opacity-80">
      {children}
    </a>
  ),
  table: ({ children }) => (
    <div className="my-2 overflow-x-auto">
      <table className="min-w-full text-xs border-collapse">{children}</table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-muted/50">{children}</thead>
  ),
  th: ({ children }) => (
    <th className="border border-border px-2 py-1 text-left font-semibold">{children}</th>
  ),
  td: ({ children }) => (
    <td className="border border-border px-2 py-1">{children}</td>
  ),
  strong: ({ children }) => (
    <strong className="font-semibold">{children}</strong>
  ),
}

export const MarkdownContent = memo(function MarkdownContent({ content }: { content: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  )
})
