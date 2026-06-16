import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  BarChart3,
  Download,
  Calendar,
  ChevronDown,
  TrendingUp,
  TrendingDown,
  Activity,
  Zap,
  MousePointerClick,
  Server,
} from 'lucide-react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts'
import LoadingSpinner from '../components/LoadingSpinner'
import { api, mock, isMockData } from '../lib/api-client'
import { useAppContext } from './__root'

const METRICS = [
  { value: 'api_calls', label: 'API Calls', icon: Activity },
  { value: 'active_users', label: 'Active Users', icon: Server },
  { value: 'response_time', label: 'Response Time', icon: Zap },
  { value: 'error_rate', label: 'Error Rate', icon: TrendingDown },
]

export function AnalyticsPage() {
  const { setBackendOffline } = useAppContext()
  const [selectedMetric, setSelectedMetric] = useState('api_calls')
  const [showMetricPicker, setShowMetricPicker] = useState(false)

  const usageQuery = useQuery({
    queryKey: ['usage', mock.customerId, selectedMetric],
    queryFn: () => api.usageAnalytics(mock.customerId, selectedMetric),
  })

  if (isMockData(usageQuery.data as any)) {
    setBackendOffline(true)
  }

  const usageData = usageQuery.data?.success
    ? usageQuery.data.data
    : {
        ...mock.usageData,
        metric_name: selectedMetric,
        data_points: generateMockDataPoints(selectedMetric),
      }

  const isLoading = usageQuery.isLoading

  // Stats derived from data
  const dataPoints = usageData?.data_points ?? []
  const total = usageData?.total ?? 0
  const avg =
    dataPoints.length > 0
      ? Math.round(dataPoints.reduce((s, p) => s + p.value, 0) / dataPoints.length)
      : 0
  const max = dataPoints.length > 0 ? Math.max(...dataPoints.map((p) => p.value)) : 0
  const min = dataPoints.length > 0 ? Math.min(...dataPoints.map((p) => p.value)) : 0
  const trend =
    dataPoints.length >= 2
      ? dataPoints[dataPoints.length - 1].value - dataPoints[0].value
      : 0
  const trendPositive = trend >= 0

  const selectedMetricLabel =
    METRICS.find((m) => m.value === selectedMetric)?.label ?? selectedMetric
  const SelectedIcon =
    METRICS.find((m) => m.value === selectedMetric)?.icon ?? Activity

  if (isLoading) {
    return <LoadingSpinner fullPage message="Loading analytics..." />
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-rose-50 dark:bg-rose-950/30">
            <BarChart3 size={20} className="text-rose-600 dark:text-rose-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
              Usage Analytics
            </h1>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Track and analyze your usage metrics
            </p>
          </div>
        </div>
        <button className="btn-secondary text-xs">
          <Download size={14} />
          Export Data
        </button>
      </div>

      {/* Metric Selector */}
      <div className="relative">
        <button
          onClick={() => setShowMetricPicker(!showMetricPicker)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-sm font-medium text-gray-700 dark:text-gray-300 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
        >
          <SelectedIcon size={16} />
          {selectedMetricLabel}
          <ChevronDown size={16} className="text-gray-400" />
        </button>
        {showMetricPicker && (
          <>
            <div
              className="fixed inset-0 z-10"
              onClick={() => setShowMetricPicker(false)}
            />
            <div className="absolute top-full left-0 mt-1 w-48 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-lg z-20 py-1">
              {METRICS.map((metric) => {
                const Icon = metric.icon
                return (
                  <button
                    key={metric.value}
                    onClick={() => {
                      setSelectedMetric(metric.value)
                      setShowMetricPicker(false)
                    }}
                    className={`w-full flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                      selectedMetric === metric.value
                        ? 'text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950/30'
                        : 'text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700'
                    }`}
                  >
                    <Icon size={16} />
                    {metric.label}
                  </button>
                )
              })}
            </div>
          </>
        )}
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <SummaryCard
          label="Total"
          value={total.toLocaleString()}
          icon={Activity}
          color="brand"
        />
        <SummaryCard
          label="Average"
          value={avg.toLocaleString()}
          icon={BarChart3}
          color="emerald"
        />
        <SummaryCard
          label="Peak"
          value={max.toLocaleString()}
          icon={TrendingUp}
          color="violet"
        />
        <SummaryCard
          label="Trend"
          value={`${trendPositive ? '+' : ''}${trend.toLocaleString()}`}
          icon={trendPositive ? TrendingUp : TrendingDown}
          color={trendPositive ? 'emerald' : 'rose'}
        />
      </div>

      {/* Chart */}
      <div className="card">
        <div className="card-header flex items-center justify-between">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            {selectedMetricLabel} — Last 30 Days
          </h2>
          <span className="flex items-center gap-1 text-xs text-gray-400 dark:text-gray-500">
            <Calendar size={12} />
            Daily
          </span>
        </div>
        <div className="card-body">
          {dataPoints.length === 0 ? (
            <div className="text-center py-16 text-sm text-gray-400">
              No data available for this metric.
            </div>
          ) : (
            <div className="h-[350px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={dataPoints} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
                  <defs>
                    <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="#e5e7eb"
                    className="dark:opacity-20"
                  />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11, fill: '#9ca3af' }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(val) => {
                      const d = new Date(val)
                      return `${d.getMonth() + 1}/${d.getDate()}`
                    }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: '#9ca3af' }}
                    tickLine={false}
                    axisLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: '#1e293b',
                      border: 'none',
                      borderRadius: '8px',
                      color: '#f1f5f9',
                      fontSize: '12px',
                    }}
                    labelFormatter={(val) => new Date(val).toLocaleDateString()}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    fill="url(#colorValue)"
                    dot={false}
                    activeDot={{ r: 4, fill: '#3b82f6' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Data Table */}
      <div className="card">
        <div className="card-header">
          <h2 className="text-base font-semibold text-gray-900 dark:text-gray-100">
            Daily Breakdown
          </h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-100 dark:border-gray-700/50">
                <th className="table-header">Date</th>
                <th className="table-header">{selectedMetricLabel}</th>
                <th className="table-header">Change</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 dark:divide-gray-700/50">
              {dataPoints.length === 0 ? (
                <tr>
                  <td colSpan={3} className="text-center py-8 text-sm text-gray-400">
                    No data available.
                  </td>
                </tr>
              ) : (
                dataPoints.map((point, idx) => {
                  const prev = idx > 0 ? dataPoints[idx - 1].value : point.value
                  const change = point.value - prev
                  const changePct =
                    prev > 0 ? ((change / prev) * 100).toFixed(1) : '0'

                  return (
                    <tr
                      key={point.date}
                      className="hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                    >
                      <td className="table-cell whitespace-nowrap font-medium">
                        {new Date(point.date).toLocaleDateString('en-US', {
                          weekday: 'short',
                          month: 'short',
                          day: 'numeric',
                        })}
                      </td>
                      <td className="table-cell">
                        <span className="font-semibold">
                          {point.value.toLocaleString()}
                        </span>
                      </td>
                      <td className="table-cell">
                        <span
                          className={`inline-flex items-center gap-1 text-xs font-medium ${
                            change > 0
                              ? 'text-emerald-600 dark:text-emerald-400'
                              : change < 0
                                ? 'text-rose-600 dark:text-rose-400'
                                : 'text-gray-400'
                          }`}
                        >
                          {change !== 0 && (
                            <svg
                              width="10"
                              height="10"
                              viewBox="0 0 10 10"
                              fill="none"
                              className={
                                change > 0 ? '' : 'rotate-180'
                              }
                            >
                              <path
                                d="M5 1.5L8.5 7H1.5L5 1.5Z"
                                fill="currentColor"
                              />
                            </svg>
                          )}
                          {change > 0 ? '+' : ''}
                          {changePct}%
                        </span>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// ---- Sub-components --------------------------------------------------------

function SummaryCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string
  value: string
  icon: any
  color: 'brand' | 'emerald' | 'violet' | 'rose'
}) {
  const colorMap = {
    brand: 'text-brand-600 dark:text-brand-400 bg-brand-50 dark:bg-brand-950/30',
    emerald: 'text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30',
    violet: 'text-violet-600 dark:text-violet-400 bg-violet-50 dark:bg-violet-950/30',
    rose: 'text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/30',
  }

  return (
    <div className="card p-4">
      <div className="flex items-center gap-3 mb-2">
        <div className={`p-2 rounded-lg ${colorMap[color]}`}>
          <Icon size={16} />
        </div>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 mb-0.5">{label}</p>
      <p className="text-xl font-bold text-gray-900 dark:text-gray-100">{value}</p>
    </div>
  )
}

function generateMockDataPoints(metric: string) {
  const base =
    metric === 'api_calls'
      ? 500
      : metric === 'active_users'
        ? 120
        : metric === 'response_time'
          ? 45
          : 2.5
  const variance =
    metric === 'error_rate' ? 0.5 : metric === 'response_time' ? 10 : 100

  return Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400000).toISOString().slice(0, 10),
    value: Math.max(
      0,
      Math.round(base + (Math.random() - 0.5) * variance),
    ),
  }))
}
