/**
 * ChatPanel — In-game chat interface for the RAG-powered AI referee.
 *
 * Provides a scrollable message feed and an input field for asking
 * rules questions.  The AI referee uses retrieval-augmented generation
 * (Ollama LLM + ChromaDB) to answer questions about the game rules
 * and current board state.
 *
 * Features:
 *   - Auto-scrolls to the latest message
 *   - Shows loading dots while the LLM is processing
 *   - Renders referee responses with lightweight Markdown support
 *     (bold, italic, inline code, headings, lists, paragraphs)
 *   - User messages are displayed as plain text
 */

import { useRef, useEffect, useState } from 'react'

// ---------------------------------------------------------------------------
// Lightweight Markdown renderer
// ---------------------------------------------------------------------------

/**
 * Parse inline Markdown formatting within a single line of text.
 * Supports: **bold**, *italic*, `inline code`.
 *
 * Returns an array of strings and React elements.
 */
function inlineFormat(str) {
  const parts = []
  const re = /(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`)/g
  let last = 0, i = 0, m
  while ((m = re.exec(str)) !== null) {
    if (m.index > last) parts.push(str.slice(last, m.index))
    if (m[2])      parts.push(<strong key={i++}>{m[2]}</strong>)
    else if (m[3]) parts.push(<em key={i++}>{m[3]}</em>)
    else if (m[4]) parts.push(<code key={i++} className="chat-md-code">{m[4]}</code>)
    last = m.index + m[0].length
  }
  if (last < str.length) parts.push(str.slice(last))
  return parts
}

/**
 * MarkdownText — renders a multi-line string with basic Markdown support.
 *
 * Supported elements:
 *   - Headings: #, ##, ### (mapped to h3–h5 to avoid semantic conflicts)
 *   - Unordered lists: - or * prefix
 *   - Ordered lists: 1. prefix
 *   - Paragraphs: any other non-empty line
 *   - Inline formatting: bold, italic, code
 */
function MarkdownText({ text }) {
  const lines = text.split('\n')
  const blocks = []
  let listItems = [], listType = null, key = 0

  /** Flush accumulated list items into a <ul> or <ol> block. */
  const flushList = () => {
    if (!listItems.length) return
    const Tag = listType === 'ol' ? 'ol' : 'ul'
    blocks.push(<Tag key={key++} className="chat-md-list">{listItems}</Tag>)
    listItems = []
    listType = null
  }

  lines.forEach(line => {
    const t = line.trim()
    if (!t) { flushList(); return }

    // Headings: # → h3, ## → h4, ### → h5
    const hMatch = t.match(/^(#{1,3})\s+(.+)/)
    if (hMatch) {
      flushList()
      const lvl = Math.min(hMatch[1].length + 2, 5)
      const Tag = `h${lvl}`
      blocks.push(<Tag key={key++} className="chat-md-heading">{inlineFormat(hMatch[2])}</Tag>)
      return
    }

    // Unordered list items: - or *
    const ulMatch = t.match(/^[-*]\s+(.+)/)
    if (ulMatch) {
      if (listType === 'ol') flushList()
      listType = 'ul'
      listItems.push(<li key={key++}>{inlineFormat(ulMatch[1])}</li>)
      return
    }

    // Ordered list items: 1. 2. etc.
    const olMatch = t.match(/^\d+\.\s+(.+)/)
    if (olMatch) {
      if (listType === 'ul') flushList()
      listType = 'ol'
      listItems.push(<li key={key++}>{inlineFormat(olMatch[1])}</li>)
      return
    }

    // Regular paragraph
    flushList()
    blocks.push(<p key={key++} className="chat-md-p">{inlineFormat(t)}</p>)
  })
  flushList()
  return <div className="chat-md">{blocks}</div>
}

// ---------------------------------------------------------------------------
// ChatPanel component
// ---------------------------------------------------------------------------

/**
 * @param {object[]} messages — Array of { from: 'user'|'referee', text, loading? }.
 * @param {function} onAsk   — Callback to submit a question to the referee.
 */
export function ChatPanel({ messages, onAsk }) {
  const [input, setInput]   = useState('')
  const bottomRef           = useRef(null)

  // Auto-scroll to the latest message when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  /** Submit the current input as a question. */
  const submit = () => {
    const q = input.trim()
    if (!q) return
    onAsk(q)
    setInput('')
  }

  return (
    <div className="chat-panel">
      <div className="chat-header">Ask the Referee</div>

      <div className="chat-messages">
        {/* Empty state prompt */}
        {messages.length === 0 && (
          <div className="chat-empty">
            Ask the referee anything about the rules or current board state.
          </div>
        )}

        {/* Message feed */}
        {messages.map((msg, i) => (
          <div key={i} className={`chat-msg chat-msg-${msg.from}`}>
            <span className="chat-msg-label">
              {msg.from === 'user' ? 'You' : 'Referee'}
            </span>
            <span className={`chat-msg-text${msg.loading ? ' loading' : ''}`}>
              {msg.loading
                ? <LoadingDots />
                : msg.from === 'referee'
                ? <MarkdownText text={msg.text} />
                : msg.text}
            </span>
          </div>
        ))}
        {/* Scroll anchor */}
        <div ref={bottomRef} />
      </div>

      {/* Input row */}
      <div className="chat-input-row">
        <input
          className="chat-input"
          placeholder="Ask a rules question…"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
        />
        <button className="btn btn-small btn-primary" onClick={submit}>Ask</button>
      </div>
    </div>
  )
}

/** Animated loading dots indicator shown while the LLM is processing. */
function LoadingDots() {
  return <span className="loading-dots"><span>.</span><span>.</span><span>.</span></span>
}
