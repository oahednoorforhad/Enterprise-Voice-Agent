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
    color: 'text-brand-blue',
    bgColor: 'bg-blue-50 dark:bg-blue-950/30',
  },
  policies: {
    label: 'Policies',
    icon: FileText,
    color: 'text-brand-coral',
    bgColor: 'bg-coral-50 dark:bg-coral-900/20',
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
          <div key={i} className="card-flat p-4">
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
        <h3 className="font-display text-heading-feature text-ink dark:text-gray-100 mb-1">
          No results found
        </h3>
        <p className="text-caption text-muted-slate">
          Try adjusting your search query or browse different topics.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 mb-2">
        <Icon size={16} className={config.color} />
        <span className="text-caption font-medium text-muted-slate">
          {config.label} ({results.length})
        </span>
      </div>
      {results.map((result, idx) => {
        const isExpanded = expandedIndex === idx
        const relevancePct = Math.round(result.relevance * 100)

        return (
          <div
            key={`${source}-${idx}`}
            className="card-flat overflow-hidden transition-all duration-200"
          >
            <button
              className="w-full text-left px-5 py-4 flex items-start justify-between gap-3 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
              onClick={() => setExpandedIndex(isExpanded ? null : idx)}
            >
              <div className="flex-1 min-w-0">
                <h4 className="text-body-small font-semibold text-ink dark:text-gray-100 truncate">
                  {result.title}
                </h4>
                <p className="text-caption text-muted-slate mt-0.5">
                  Source: {result.source}
                </p>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0">
                <span
                  className={`text-micro font-medium px-2 py-0.5 rounded-pill ${
                    relevancePct >= 90
                      ? 'chip-green'
                      : relevancePct >= 70
                        ? 'chip-amber'
                        : 'chip-gray'
                  }`}
                >
                  {relevancePct}%
                </span>
                {isExpanded ? (
                  <ChevronDown size={16} className="text-muted-slate" />
                ) : (
                  <ChevronRight size={16} className="text-muted-slate" />
                )}
              </div>
            </button>
            {isExpanded && (
              <div className="px-5 pb-4 animate-slide-up">
                <div className="border-t border-hairline dark:border-white/5 pt-3">
                  <p className="text-caption text-muted-slate leading-relaxed">
                    {result.content}
                  </p>
                  <div className="flex items-center gap-2 mt-3">
                    <span className="chip-blue text-[11px] py-0.5">{result.source}</span>
                    <span className="text-caption text-muted-slate">
                      Relevance: {relevancePct}%
                    </span>
                    <button className="ml-auto text-caption text-brand-blue hover:underline inline-flex items-center gap-1">
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
