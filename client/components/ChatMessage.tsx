import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Message } from '../../types/Message'

interface ChatMessageProps {
  message: Message
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === 'user'

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
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
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
