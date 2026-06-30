import React, { useState, useRef, useEffect } from 'react';

// Effect moved inside component

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import toast from 'react-hot-toast';
import { Message } from '../../types/Message';

interface ChatMessageProps {
  message: Message;
}

const ChatMessage: React.FC<ChatMessageProps> = ({ message }) => {
  const rootRef = useRef<HTMLDivElement>(null);

  // Cleanup stray label elements from previous renders (StrictMode double rendering)
  useEffect(() => {
    const labels = document.querySelectorAll('.message-role-label');
    labels.forEach(label => label.remove());
  }, []);




  const [showFull, setShowFull] = useState(false);

  const isUser = message.role === 'user';
  const isLong = !isUser && message.content.length > 300;
  const displayedContent = isUser || !isLong || showFull ? message.content : `${message.content.slice(0, 300)}...`;

  return (
    <div ref={rootRef} className={`message ${isUser ? 'user-message' : 'assistant-message'}`}>
      <div className="message-content">
        <span className="message-role-label">{isUser ? 'You' : 'MemAI'}</span>
        <div className="message-text">
          {isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                code({ className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  const codeString = String(children).replace(/\n$/, '');
                  const copyCode = () => {
                    navigator.clipboard.writeText(codeString);
                    toast.success('Code copied');
                  };
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
                        aria-label="Copy code"
                      >
                        Copy
                      </button>
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
                  );
                },
              }}
            >
              {displayedContent}
            </ReactMarkdown>
          )}
          {isLong && !showFull && (
            <button onClick={() => setShowFull(true)} className="show-more-btn">
              Show full response
            </button>
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
  );
};

export default ChatMessage;
