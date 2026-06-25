import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { Message } from '../../types/Message'
import { useState } from 'react'
import toast from 'react-hot-toast'

interface ChatMessageProps {
  message: Message
}

export const ChatMessage = ({ message }: ChatMessageProps) => {
  const isUser = message.role === 'user'

  const [showFull, setShowFull] = useState(false)

  const isLong = !isUser && message.content.length > 300
  const displayedContent = isUser ? message.content : (isLong && !showFull ? message.content.slice(0, 300) + '…' : message.content)

  return (
    <div
      className={`message ${isUser ? 'user-message' : 'assistant-message'}`}
    >
      <div className="message-content">
        <div className="message-role">{isUser ? 'You' : 'MemAI'}</div>
        <div className="message-text">
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '')
                  const codeString = String(children).replace(/\n$/, '')
                  const copyCode = () => {
                    navigator.clipboard.writeText(codeString)
                    toast.success('已复制代码')
                  }
                  return match ? (
                    <div style={{ position: 'relative' }}>
                      <button
                        onClick={copyCode}
                        style={{
                          position: 'absolute',
                          top: 4,
                          right: 4,
                          background: 'rgba(0,0,0,0.3)',
                          color: '#fff',
                          border: 'none',
                          borderRadius: 4,
                          padding: '2px 6px',
                          cursor: 'pointer',
                          fontSize: '0.75rem',
                        }}
                        aria-label="复制代码"
                      >复制</button>
                      <SyntaxHighlighter
                        {...props}
                        children={codeString}
                        style={vscDarkPlus as any}
                        language={match[1]}
                        PreTag="div"
                      />
                    </div>
                  ) : (
                    <code {...props} className={className}>
                      {children}
                    </code>
                  )
                }
              }}
            >
              {displayedContent}
            </ReactMarkdown>
          )}
          {/* 显示折叠/展开按钮 */}
          {isLong && !showFull && (
            <button
              onClick={() => setShowFull(true)}
              className="show-more-btn"
            >展开全部</button>
          )}
        </div>
        {!isUser && message.sources && message.sources.length > 0 && (
          <div className="message-sources">
            <span className="sources-label">📎 Sources:</span>
            {message.sources.map((source, i) => (
              <span key={i} className="source-tag">
                {source.file} (p.{source.page})
              </span>
            ))}
          </div>
        )}
        <div className="message-timestamp">
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  )
}
