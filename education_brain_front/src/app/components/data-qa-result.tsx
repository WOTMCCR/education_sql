import type { ReactNode } from 'react'
import {
  AlertTriangle,
  BarChart3,
  ChevronDown,
  Database,
  FileWarning,
  LineChart as LineChartIcon,
  Sigma,
  Table2,
  Timer,
  Workflow,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  XAxis,
  YAxis,
} from 'recharts'
import type { DataQaResult } from '../types/data-qa'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from './ui/chart'
import { cn } from './ui/utils'

type DataQaVisualModel = DataQaResult['visual']
type DataQaColumn = DataQaVisualModel['columns'][number]
type DataQaRow = DataQaVisualModel['rows'][number]
type DataQaTraceStage = DataQaResult['trace']['stages'][number]

const chartColors = [
  'var(--chart-1)',
  'var(--chart-2)',
  'var(--chart-3)',
  'var(--chart-4)',
  'var(--chart-5)',
]

export function DataQaResultView({ result }: { result: DataQaResult }) {
  const visualIcon = getVisualIcon(result.visual.type)

  return (
    <section className="w-full min-w-0 rounded-lg border border-border bg-background text-sm">
      <header className="flex flex-col gap-2 border-b border-border px-3 py-2.5 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <div className="flex min-w-0 items-center gap-2">
            {visualIcon}
            <h3 className="min-w-0 truncate text-sm font-medium">
              {result.visual.title || '数据问数结果'}
            </h3>
          </div>
          {result.answer ? (
            <p className="mt-1 break-words text-xs leading-5 text-muted-foreground">
              {result.answer}
            </p>
          ) : null}
        </div>
        <div className="flex shrink-0 flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
          <MetaPill icon={<Database className="h-3 w-3" />}>
            {result.trace.rowCount.toLocaleString()} 行
          </MetaPill>
          <MetaPill icon={<Timer className="h-3 w-3" />}>
            {result.trace.durationMs.toLocaleString()} ms
          </MetaPill>
        </div>
      </header>

      <div className="space-y-3 p-3">
        {result.error ? <ErrorBanner error={result.error} /> : null}
        {result.warnings.length > 0 ? (
          <WarningList warnings={result.warnings} />
        ) : null}

        <DataQaVisual visual={result.visual} />

        <DataQaExplainPanel
          explain={result.explain}
          trace={result.trace}
          queryId={result.queryId}
        />
      </div>
    </section>
  )
}

function DataQaVisual({ visual }: { visual: DataQaVisualModel }) {
  if (visual.type === 'stat') {
    return <DataQaStat visual={visual} />
  }

  if (visual.type === 'line' || visual.type === 'bar') {
    return <DataQaChart visual={visual} />
  }

  return <DataQaTable columns={visual.columns} rows={visual.rows} />
}

function DataQaStat({ visual }: { visual: DataQaVisualModel }) {
  const firstRow = visual.rows[0]
  const valueColumn =
    visual.columns.find((column) => column.type !== 'string' && firstRow?.[column.key] !== undefined) ||
    visual.columns[1] ||
    visual.columns[0]
  const labelColumn =
    visual.columns.find((column) => column.key !== valueColumn?.key) ||
    visual.columns[0]

  if (!firstRow || !valueColumn) {
    return <DataQaTable columns={visual.columns} rows={visual.rows} />
  }

  return (
    <div className="rounded-md border border-border bg-muted/20 px-3 py-3">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div className="min-w-0">
          <p className="text-xs text-muted-foreground">{valueColumn.label}</p>
          <p className="mt-1 break-words font-mono text-2xl font-semibold tabular-nums text-foreground sm:text-3xl">
            {formatValue(firstRow[valueColumn.key], valueColumn)}
          </p>
        </div>
        {labelColumn && labelColumn.key !== valueColumn.key ? (
          <div className="min-w-0 text-xs text-muted-foreground sm:text-right">
            <span className="block">{labelColumn.label}</span>
            <span className="block truncate font-medium text-foreground">
              {formatValue(firstRow[labelColumn.key], labelColumn)}
            </span>
          </div>
        ) : null}
      </div>

      {visual.rows.length > 1 ? (
        <div className="mt-3 border-t border-border pt-3">
          <DataQaTable columns={visual.columns} rows={visual.rows} compact />
        </div>
      ) : null}
    </div>
  )
}

function DataQaChart({ visual }: { visual: DataQaVisualModel }) {
  const xKey = visual.x || visual.columns[0]?.key
  const yKeys = getYKeys(visual)

  if (!xKey || yKeys.length === 0 || visual.rows.length === 0) {
    return <DataQaTable columns={visual.columns} rows={visual.rows} />
  }

  const config = yKeys.reduce<ChartConfig>((acc, key) => {
    acc[key] = {
      label: visual.columns.find((column) => column.key === key)?.label || key,
    }
    return acc
  }, {})

  return (
    <div className="space-y-2">
      <ChartContainer config={config} className="h-56 w-full aspect-auto">
        {visual.type === 'line' ? (
          <LineChart data={visual.rows} margin={{ left: 0, right: 8, top: 8, bottom: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey={xKey}
              tickLine={false}
              axisLine={false}
              minTickGap={24}
              tickFormatter={(value) => formatAxisValue(value)}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(value) => formatCompactNumber(value)}
            />
            <ChartTooltip content={<ChartTooltipContent />} />
            {yKeys.map((key, index) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={chartColors[index % chartColors.length]}
                strokeWidth={2}
                dot={visual.rows.length <= 12}
                activeDot={{ r: 4 }}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart data={visual.rows} margin={{ left: 0, right: 8, top: 8, bottom: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis
              dataKey={xKey}
              tickLine={false}
              axisLine={false}
              minTickGap={16}
              tickFormatter={(value) => formatAxisValue(value)}
            />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={48}
              tickFormatter={(value) => formatCompactNumber(value)}
            />
            <ChartTooltip content={<ChartTooltipContent />} />
            {yKeys.map((key, index) => (
              <Bar
                key={key}
                dataKey={key}
                fill={chartColors[index % chartColors.length]}
                radius={[4, 4, 0, 0]}
                maxBarSize={42}
              />
            ))}
          </BarChart>
        )}
      </ChartContainer>

      <DataQaTable columns={visual.columns} rows={visual.rows} compact />
    </div>
  )
}

function DataQaTable({
  columns,
  rows,
  compact = false,
}: {
  columns: DataQaColumn[]
  rows: DataQaRow[]
  compact?: boolean
}) {
  if (columns.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-border px-3 py-4 text-center text-xs text-muted-foreground">
        暂无可展示字段
      </div>
    )
  }

  return (
    <div className="w-full min-w-0 overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-max border-collapse text-left text-xs">
        <thead className="bg-muted/50 text-muted-foreground">
          <tr>
            {columns.map((column) => (
              <th key={column.key} className="whitespace-nowrap px-2.5 py-2 font-medium">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-2.5 py-4 text-center text-muted-foreground">
                暂无数据
              </td>
            </tr>
          ) : (
            rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="border-t border-border">
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn(
                      'max-w-[16rem] break-words px-2.5 py-2 align-top',
                      compact && 'py-1.5',
                      column.type !== 'string' && 'font-mono tabular-nums',
                    )}
                  >
                    {formatValue(row[column.key], column)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

function DataQaExplainPanel({
  explain,
  trace,
  queryId,
}: {
  explain: DataQaResult['explain']
  trace: DataQaResult['trace']
  queryId: string
}) {
  return (
    <details className="group rounded-md border border-border bg-muted/20">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-xs font-medium">
        <span className="flex min-w-0 items-center gap-2">
          <Workflow className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          <span className="truncate">SQL / 口径 / Trace</span>
        </span>
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
      </summary>
      <div className="space-y-3 border-t border-border p-3">
        <KeyValueGrid
          items={[
            ['Query ID', queryId],
            ['Metrics', explain.metrics.length.toLocaleString()],
            ['Tables', explain.tables.length.toLocaleString()],
            ['Trace', `${trace.stages.length.toLocaleString()} stages`],
          ]}
        />

        {explain.sql ? (
          <DebugBlock title="SQL" icon={<Database className="h-3.5 w-3.5" />}>
            <pre className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded bg-background px-2.5 py-2 font-mono text-[11px] leading-4">
              {explain.sql}
            </pre>
          </DebugBlock>
        ) : null}

        {explain.metrics.length > 0 ? (
          <DebugBlock title="指标口径" icon={<Sigma className="h-3.5 w-3.5" />}>
            <div className="space-y-2">
              {explain.metrics.map((metric) => (
                <div key={metric.id} className="rounded border border-border bg-background px-2.5 py-2">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-medium">{metric.name}</span>
                    <span className="font-mono text-[11px] text-muted-foreground">{metric.id}</span>
                    {metric.unit ? (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                        {metric.unit}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 break-words font-mono text-[11px] text-muted-foreground">
                    {metric.formula}
                  </p>
                  <p className="mt-1 break-words text-[11px] text-muted-foreground">
                    {metric.description}
                  </p>
                </div>
              ))}
            </div>
          </DebugBlock>
        ) : null}

        <DebugBlock title="表 / 列 / Join" icon={<Table2 className="h-3.5 w-3.5" />}>
          <TagList label="Tables" values={explain.tables} />
          <TagList label="Columns" values={explain.columns} />
          <TagList label="Joins" values={explain.joins} />
          <TagList label="Assumptions" values={explain.assumptions} />
        </DebugBlock>

        <DebugBlock title="Trace" icon={<Timer className="h-3.5 w-3.5" />}>
          <div className="space-y-1">
            {trace.stages.map((stage, index) => (
              <TraceStageRow key={`${stage.name}-${index}`} stage={stage} />
            ))}
          </div>
        </DebugBlock>
      </div>
    </details>
  )
}

function ErrorBanner({ error }: { error: DataQaResult['error'] }) {
  if (!error) {
    return null
  }

  return (
    <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">
      <div className="flex items-start gap-2">
        <FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0">
          <p className="break-words font-medium">
            {error.code} · {error.stage}
          </p>
          <p className="mt-1 break-words">{error.message}</p>
        </div>
      </div>
    </div>
  )
}

function WarningList({ warnings }: { warnings: string[] }) {
  return (
    <div className="rounded-md border border-orange-200 bg-orange-50 px-3 py-2 text-xs text-orange-800">
      <div className="flex items-start gap-2">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <div className="min-w-0 space-y-1">
          {warnings.map((warning, index) => (
            <p key={index} className="break-words">
              {warning}
            </p>
          ))}
        </div>
      </div>
    </div>
  )
}

function TraceStageRow({ stage }: { stage: DataQaTraceStage }) {
  return (
    <div className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-2 rounded bg-background px-2.5 py-1.5 text-[11px]">
      <span
        className={cn(
          'mt-1 h-2 w-2 rounded-full',
          stage.status === 'ok' && 'bg-green-500',
          stage.status === 'error' && 'bg-destructive',
          stage.status === 'skipped' && 'bg-muted-foreground/40',
        )}
      />
      <div className="min-w-0">
        <p className="truncate font-mono">{stage.name}</p>
        {stage.message ? (
          <p className="break-words text-muted-foreground">{stage.message}</p>
        ) : null}
      </div>
      <span className="font-mono text-muted-foreground">
        {stage.durationMs === undefined ? stage.status : `${stage.durationMs} ms`}
      </span>
    </div>
  )
}

function DebugBlock({
  title,
  icon,
  children,
}: {
  title: string
  icon: ReactNode
  children: ReactNode
}) {
  return (
    <section className="space-y-1.5">
      <h4 className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        {icon}
        {title}
      </h4>
      {children}
    </section>
  )
}

function KeyValueGrid({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="min-w-0 rounded bg-background px-2.5 py-2">
          <p className="truncate text-[10px] uppercase text-muted-foreground">{label}</p>
          <p className="mt-0.5 truncate font-mono text-xs">{value}</p>
        </div>
      ))}
    </div>
  )
}

function TagList({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="mb-2 last:mb-0">
      <p className="mb-1 text-[11px] text-muted-foreground">{label}</p>
      {values.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {values.map((value, index) => (
            <span
              key={`${value}-${index}`}
              className="max-w-full break-words rounded bg-background px-1.5 py-0.5 font-mono text-[11px]"
            >
              {value}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-[11px] text-muted-foreground">无</p>
      )}
    </div>
  )
}

function MetaPill({ icon, children }: { icon: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5">
      {icon}
      <span className="whitespace-nowrap">{children}</span>
    </span>
  )
}

function getYKeys(visual: DataQaVisualModel) {
  if (visual.y?.length) {
    return visual.y.filter((key) => visual.columns.some((column) => column.key === key))
  }

  return visual.columns
    .filter((column) => column.key !== visual.x && ['number', 'percent', 'currency'].includes(column.type))
    .map((column) => column.key)
}

function getVisualIcon(type: DataQaVisualModel['type']) {
  const className = 'h-4 w-4 shrink-0 text-muted-foreground'

  if (type === 'line') {
    return <LineChartIcon className={className} />
  }

  if (type === 'bar') {
    return <BarChart3 className={className} />
  }

  if (type === 'table') {
    return <Table2 className={className} />
  }

  return <Sigma className={className} />
}

function formatValue(value: unknown, column?: DataQaColumn) {
  if (value === null || value === undefined || value === '') {
    return '-'
  }

  if (typeof value === 'number') {
    return formatNumber(value, column)
  }

  if (typeof value === 'boolean') {
    return value ? 'true' : 'false'
  }

  return String(value)
}

function formatNumber(value: number, column?: DataQaColumn) {
  const precision = column?.precision ?? (Number.isInteger(value) ? 0 : 2)

  if (column?.type === 'percent') {
    return `${value.toLocaleString(undefined, {
      maximumFractionDigits: precision,
      minimumFractionDigits: precision,
    })}%`
  }

  const formatted = value.toLocaleString(undefined, {
    maximumFractionDigits: precision,
    minimumFractionDigits: column?.type === 'currency' ? precision : 0,
  })

  if (column?.type === 'currency' && column.unit === 'yuan') {
    return `¥${formatted}`
  }

  return column?.unit ? `${formatted} ${column.unit}` : formatted
}

function formatAxisValue(value: unknown) {
  const text = String(value ?? '')
  return text.length > 12 ? `${text.slice(0, 11)}…` : text
}

function formatCompactNumber(value: unknown) {
  const number = Number(value)

  if (!Number.isFinite(number)) {
    return String(value ?? '')
  }

  return Intl.NumberFormat(undefined, {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(number)
}
