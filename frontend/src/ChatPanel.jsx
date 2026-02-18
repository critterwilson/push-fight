import { useRef, useEffect, useState } from 'react'

// ---------------------------------------------------------------------------
// Lightweight markdown renderer — handles bold, italic, inline code,
// headings (#/##), unordered lists (- /*), ordered lists (1.), paragraphs.
// ---------------------------------------------------------------------------
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

function MarkdownText({ text }) {
  const lines = text.split('\n')
  const blocks = []
  let listItems = [], listType = null, key = 0

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

    const hMatch = t.match(/^(#{1,3})\s+(.+)/)
    if (hMatch) {
      flushList()
      const lvl = Math.min(hMatch[1].length + 2, 5) // # → h3, ## → h4, ### → h5
      const Tag = `h${lvl}`
      blocks.push(<Tag key={key++} className="chat-md-heading">{inlineFormat(hMatch[2])}</Tag>)
      return
    }

    const ulMatch = t.match(/^[-*]\s+(.+)/)
    if (ulMatch) {
      if (listType === 'ol') flushList()
      listType = 'ul'
      listItems.push(<li key={key++}>{inlineFormat(ulMatch[1])}</li>)
      return
    }

    const olMatch = t.match(/^\d+\.\s+(.+)/)
    if (olMatch) {
      if (listType === 'ul') flushList()
      listType = 'ol'
      listItems.push(<li key={key++}>{inlineFormat(olMatch[1])}</li>)
      return
    }

    flushList()
    blocks.push(<p key={key++} className="chat-md-p">{inlineFormat(t)}</p>)
  })
  flushList()
  return <div className="chat-md">{blocks}</div>
}

export function ChatPanel({ messages, onAsk }) {
  const [input, setInput]   = useState('')
  const bottomRef           = useRef(null)

  // Auto-scroll to latest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

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
        {messages.length === 0 && (
          <div className="chat-empty">
            Ask the referee anything about the rules or current board state.
          </div>
        )}
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
        <div ref={bottomRef} />
      </div>

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

function LoadingDots() {
  return <span className="loading-dots"><span>.</span><span>.</span><span>.</span></span>
}
