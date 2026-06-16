import { useState, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Search, BookOpen, FileText, AlertCircle, Bookmark } from 'lucide-react'
import SearchResults from '../components/SearchResults'
import { api, mock, isMockData } from '../lib/api-client'
import { useAppContext } from './__root'

type TabType = 'documentation' | 'policies'

export function KnowledgePage() {
  const { setBackendOffline } = useAppContext()
  const [query, setQuery] = useState('')
  const [activeTab, setActiveTab] = useState<TabType>('documentation')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  const docsQuery = useQuery({
    queryKey: ['knowledge-docs', submittedQuery],
    queryFn: () => api.knowledgeDocs(submittedQuery),
    enabled: submittedQuery.length > 0 && activeTab === 'documentation',
  })

  const policiesQuery = useQuery({
    queryKey: ['knowledge-policies', submittedQuery],
    queryFn: () => api.knowledgePolicies(submittedQuery),
    enabled: submittedQuery.length > 0 && activeTab === 'policies',
  })

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    const trimmed = query.trim()
    if (!trimmed) return
    setSubmittedQuery(trimmed)
  }

  // Determine which results to show
  const isDocs = activeTab === 'documentation'
  const currentQuery = isDocs ? docsQuery : policiesQuery
  const mockResults = isDocs ? mock.docsResults : mock.policyResults

  const results =
    submittedQuery === ''
      ? []
      : currentQuery.data?.success
        ? (currentQuery.data.data ?? [])
        : isMockData(currentQuery.data as any)
          ? (() => {
              setBackendOffline(true)
              return mockResults
            })()
          : mockResults

  const isLoading = currentQuery.isLoading && submittedQuery !== ''

  return (
    <div className="animate-fade-in max-w-4xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="p-2 rounded-lg bg-violet-50 dark:bg-violet-950/30">
          <BookOpen size={20} className="text-violet-600 dark:text-violet-400" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-900 dark:text-gray-100">
            Knowledge Base
          </h1>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Search documentation and policy references
          </p>
        </div>
      </div>

      {/* Search */}
      <form onSubmit={handleSearch} className="mb-6">
        <div className="relative">
          <Search
            size={18}
            className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400 dark:text-gray-500"
          />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search documentation and policies..."
            className="input pl-11 pr-24 py-3 text-base"
          />
          <button
            type="submit"
            disabled={!query.trim() || isLoading}
            className="absolute right-2 top-1/2 -translate-y-1/2 btn-primary text-xs px-3 py-1.5"
          >
            {isLoading ? 'Searching...' : 'Search'}
          </button>
        </div>
      </form>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 p-1 rounded-lg bg-gray-100 dark:bg-gray-800 w-fit">
        {([
          { id: 'documentation' as TabType, label: 'Documentation', icon: BookOpen },
          { id: 'policies' as TabType, label: 'Policies', icon: FileText },
        ]).map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id)
              setSubmittedQuery('')
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
              activeTab === tab.id
                ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 shadow-sm'
                : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            <tab.icon size={16} />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Results */}
      {submittedQuery === '' ? (
        <div className="text-center py-16">
          <div className="inline-flex p-4 rounded-full bg-gray-100 dark:bg-gray-800 mb-4">
            <Search size={32} className="text-gray-400 dark:text-gray-500" />
          </div>
          <h2 className="text-lg font-semibold text-gray-700 dark:text-gray-300 mb-2">
            Search the Knowledge Base
          </h2>
          <p className="text-sm text-gray-400 dark:text-gray-500 max-w-md mx-auto">
            Enter a search term above to find relevant documentation articles or
            policy documents.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {['billing', 'subscription', 'API', 'setup', 'SLA', 'privacy'].map(
              (tag) => (
                <button
                  key={tag}
                  onClick={() => {
                    setQuery(tag)
                    setSubmittedQuery(tag)
                  }}
                  className="px-3 py-1.5 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                >
                  {tag}
                </button>
              ),
            )}
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Result summary */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Showing results for{' '}
              <span className="font-medium text-gray-700 dark:text-gray-300">
                &ldquo;{submittedQuery}&rdquo;
              </span>
            </p>
            <span className="text-xs text-gray-400 dark:text-gray-500">
              {results.length} result{results.length !== 1 ? 's' : ''}
            </span>
          </div>

          {isLoading ? (
            <SearchResults results={[]} source={activeTab} loading />
          ) : (
            <SearchResults results={results} source={activeTab} />
          )}
        </div>
      )}

      {/* Quick Reference */}
      <div className="mt-10 card">
        <div className="card-header">
          <h3 className="text-sm font-semibold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Bookmark size={14} className="text-brand-500" />
            Quick Reference
          </h3>
        </div>
        <div className="card-body">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {[
              { title: 'Getting Started', desc: 'Setup guide and initial configuration', href: '#' },
              { title: 'API Reference', desc: 'Complete endpoint documentation', href: '#' },
              { title: 'Billing FAQ', desc: 'Common billing questions and answers', href: '#' },
              { title: 'SLA Terms', desc: 'Service level agreement details', href: '#' },
            ].map((item) => (
              <a
                key={item.title}
                href={item.href}
                className="block p-3 rounded-lg border border-gray-100 dark:border-gray-700/50 hover:border-brand-200 dark:hover:border-brand-800 hover:bg-brand-50/50 dark:hover:bg-brand-950/20 transition-all group"
              >
                <p className="text-sm font-medium text-gray-900 dark:text-gray-100 group-hover:text-brand-600 dark:group-hover:text-brand-400">
                  {item.title}
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                  {item.desc}
                </p>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
