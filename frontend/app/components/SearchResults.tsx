import { FileText, BookOpen, ExternalLink, ChevronDown, ChevronRight } from 'lucide-react'
import { useState } from 'react'
import type { KnowledgeResult } from '../lib/api-client'

interface SearchResultsProps {
  results: KnowledgeResult[]
  source: 'documentation' | 'policies'
  loading?: boolean
}

const sourceConfig = {
  documentation: {
    label: 'Documentation',
    icon: BookOpen,
    color: 'text-blue-600 dark:text-blue-400',
    bgColor: 'bg-blue-50 dark:bg-blue-950/30',
  },
  policies: {
    label: 'Policies',
    icon: FileText,
    color: 'text-violet-600 dark:text-violet-400',
    bgColor: 'bg-violet-50 dark:bg-violet-950/30',
  },
}

export default function SearchResults({ results, source, loading }: SearchResultsProps) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null)
  const config = sourceConfig[source]
  const Icon = config.icon

  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3].map((i) => (
          <div key={i} className="card p-4">
            <div className="skeleton h-5 w-3/4 mb-2" />
            <div className="skeleton h-4 w-1/2 mb-2" />
            <div className="skeleton h-4 w-full" />
          </div>
        ))}
      </div>
    )
  }

  if (results.length === 0) {
    return (
      <div className="text-center py-12">
        <div className={`inline-flex p-3 rounded-full ${config.bgColor} mb-4`}>
          <Icon size={32} className={config.color} />
        </div>
        <h3 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-1">
          No results found
        </h3>
        <p className="text-sm text-gray-400 dark:text-gray-500">
          Try adjusting your search query or browse different topics.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className={config.color} />
        <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
          {config.label} ({results.length})
        </span>
      </div>
      {results.map((result, idx) => {
        const isExpanded = expandedIndex === idx
        const relevancePct = Math.round(result.relevance * 100)

        return (
          <div
            key={`${source}-${idx}`}
            className="card overflow-hidden transition-all duration-200"
          >
            <button
              className="w-full text-left px-5 py-4 flex items-start justify-between gap-3 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
              onClick={() => setExpandedIndex(isExpanded ? null : idx)}
            >
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-semibold text-gray-900 dark:text-gray-100 truncate">
                  {result.title}
                </h4>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  Source: {result.source}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    relevancePct >= 90
                      ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                      : relevancePct >= 70
                        ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
                        : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
                  }`}
                >
                  {relevancePct}%
                </span>
                {isExpanded ? (
                  <ChevronDown size={16} className="text-gray-400" />
                ) : (
                  <ChevronRight size={16} className="text-gray-400" />
                )}
              </div>
            </button>
            {isExpanded && (
              <div className="px-5 pb-4 animate-slide-up">
                <div className="border-t border-gray-100 dark:border-gray-700/50 pt-3">
                  <p className="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
                    {result.content}
                  </p>
                  <div className="flex items-center gap-2 mt-3">
                    <span className="badge badge-info text-[10px]">{result.source}</span>
                    <span className="text-xs text-gray-400 dark:text-gray-500">
                      Relevance: {relevancePct}%
                    </span>
                    <button className="ml-auto text-xs text-brand-600 dark:text-brand-400 hover:underline inline-flex items-center gap-1">
                      View full <ExternalLink size={10} />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
