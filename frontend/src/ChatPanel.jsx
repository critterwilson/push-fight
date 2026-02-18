import { useRef, useEffect, useState } from 'react'

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
              {msg.loading ? <LoadingDots /> : msg.text}
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
