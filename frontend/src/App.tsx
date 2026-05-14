import { useState, useRef, useEffect, KeyboardEvent } from 'react'
import Markdown from 'react-markdown'
import './App.css'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

interface IngestResponse {
  video_id: string
  chunks_ingested: number
}

interface ChatResponse {
  thread_id: string
  final_answer: string | null
  status: 'waiting' | 'ended'
}

interface Message {
  role: 'user' | 'assistant' | 'error'
  content: string
}

interface IngestedVideo {
  url: string
  video_id: string
  chunks: number
  timestamp: string
}

function YoutubeIcon() {
  return (
    <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect width="28" height="28" rx="6" fill="#FF0000" />
      <polygon points="11,9 11,19 20,14" fill="white" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="7.5" stroke="var(--success)" />
      <path d="M5 8l2 2 4-4" stroke="var(--success)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SendIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
      <path d="M2 9h14M9 2l7 7-7 7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  )
}

function Spinner() {
  return <span className="spinner" aria-label="Loading" />
}

function IngestPanel() {
  const [url, setUrl] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null)
  const [history, setHistory] = useState<IngestedVideo[]>(() => {
    try { return JSON.parse(localStorage.getItem('yfcVideos') ?? '[]') } catch { return [] }
  })

  const handleIngest = async () => {
    const trimmed = url.trim()
    if (!trimmed || isLoading) return
    setIsLoading(true)
    setStatus(null)
    try {
      const res = await fetch(`${API_BASE}/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: trimmed }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Ingest failed')
      const resp = data as IngestResponse
      const entry: IngestedVideo = {
        url: trimmed,
        video_id: resp.video_id,
        chunks: resp.chunks_ingested,
        timestamp: new Date().toLocaleString(),
      }
      const updated = [entry, ...history].slice(0, 20)
      setHistory(updated)
      localStorage.setItem('yfcVideos', JSON.stringify(updated))
      setStatus({ type: 'success', message: `Ingested ${resp.chunks_ingested} chunks from ${resp.video_id}` })
      setUrl('')
    } catch (e: unknown) {
      setStatus({ type: 'error', message: e instanceof Error ? e.message : 'Unknown error' })
    } finally {
      setIsLoading(false)
    }
  }

  const handleKey = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') handleIngest()
  }

  return (
    <aside className="ingest-panel">
      <div className="panel-header">
        <h2>Add Video</h2>
        <span className="panel-subtitle">Paste a YouTube URL to index it</span>
      </div>

      <div className="input-group">
        <input
          className="text-input"
          type="url"
          placeholder="https://youtube.com/watch?v=..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={handleKey}
          disabled={isLoading}
        />
        <button className="btn btn-primary" onClick={handleIngest} disabled={isLoading || !url.trim()}>
          {isLoading ? <Spinner /> : 'Ingest'}
        </button>
      </div>

      {status && (
        <div className={`status-banner status-${status.type}`}>
          {status.type === 'success' ? <CheckIcon /> : '✕'}
          <span>{status.message}</span>
        </div>
      )}

      {history.length > 0 && (
        <div className="video-history">
          <p className="section-label">Indexed videos</p>
          <ul className="video-list">
            {history.map((v, i) => (
              <li key={i} className="video-item">
                <YoutubeIcon />
                <div className="video-info">
                  <a
                    href={`https://youtube.com/watch?v=${v.video_id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="video-id"
                  >
                    {v.video_id}
                  </a>
                  <span className="video-meta">{v.chunks} chunks · {v.timestamp}</span>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {history.length === 0 && (
        <div className="empty-state">
          <YoutubeIcon />
          <p>No videos indexed yet.<br />Paste a URL above to get started.</p>
        </div>
      )}
    </aside>
  )
}

function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [threadId, setThreadId] = useState<string | null>(null)
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, isLoading])

  const send = async () => {
    const text = input.trim()
    if (!text || isLoading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: text }])
    setIsLoading(true)
    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, thread_id: threadId }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? 'Chat request failed')
      const resp = data as ChatResponse
      setThreadId(resp.thread_id)
      if (resp.final_answer) {
        setMessages((prev) => [...prev, { role: 'assistant', content: resp.final_answer! }])
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Unknown error'
      setMessages((prev) => [...prev, { role: 'error', content: `Error: ${msg}` }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  const reset = () => {
    setMessages([])
    setThreadId(null)
    setInput('')
  }

  return (
    <section className="chat-panel">
      <div className="chat-header">
        <div>
          <h2>Ask Questions</h2>
          <span className="panel-subtitle">
            {threadId ? `Thread: ${threadId.slice(0, 8)}…` : 'New conversation'}
          </span>
        </div>
        <button className="btn btn-ghost" onClick={reset} title="New conversation">
          <PlusIcon /> New
        </button>
      </div>

      <div className="messages">
        {messages.length === 0 && !isLoading && (
          <div className="chat-empty">
            <div className="chat-empty-icon">
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                <circle cx="20" cy="20" r="19" stroke="var(--border-hover)" strokeWidth="1.5" />
                <path d="M13 20h14M20 13l7 7-7 7" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <p>Ask anything about your indexed videos.<br />
              <span className="hint">The AI will fact-check its own answers using web sources.</span>
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message message-${msg.role}`}>
            {msg.role === 'user' ? (
              <div className="bubble bubble-user">{msg.content}</div>
            ) : msg.role === 'error' ? (
              <div className="bubble bubble-error">{msg.content}</div>
            ) : (
              <div className="bubble bubble-ai">
                <div className="ai-label">
                  <CheckIcon />
                  <span>Fact-checked answer</span>
                </div>
                <Markdown>{msg.content}</Markdown>
              </div>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="message message-assistant">
            <div className="bubble bubble-ai bubble-loading">
              <Spinner />
              <span>Searching transcripts &amp; fact-checking…</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          className="chat-input"
          placeholder="Ask a question… (Enter to send, Shift+Enter for newline)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          disabled={isLoading}
          rows={1}
        />
        <button className="btn btn-send" onClick={send} disabled={isLoading || !input.trim()} aria-label="Send">
          <SendIcon />
        </button>
      </div>
    </section>
  )
}

export default function App() {
  return (
    <div className="layout">
      <header className="app-header">
        <div className="app-header-inner">
          <div className="brand">
            <YoutubeIcon />
            <span className="brand-name">YouTube Fact Checker</span>
          </div>
          <span className="brand-tagline">AI-powered answers · web fact-checked</span>
        </div>
      </header>
      <div className="content">
        <IngestPanel />
        <ChatPanel />
      </div>
    </div>
  )
}
