import { useState, useEffect, useRef, useCallback } from 'react'
import toast, { Toaster } from 'react-hot-toast'

import { useQuery, useQueryClient } from '@tanstack/react-query'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import SessionSidebar from './SessionSidebar'
import { Message, Source } from '../../types/Message'
import {
  sendMessageStream,
  getMessages,
  clearMessages,
  ErrorResponse,
} from '../apiClient'

/** Map error codes to user-friendly toast messages */
function getErrorToast(err: ErrorResponse): { message: string; duration: number } {
  switch (err.error_code) {
    case 'timeout':
      return { message: '⏱️ Request timed out — the AI service is slow right now. Please try again.', duration: 6000 }
    case 'rate_limited':
      return { message: '🚦 Too many requests — please wait a moment and try again.', duration: 6000 }
    case 'service_unavailable':
      return { message: '🔧 AI service is temporarily unavailable. Please try again shortly.', duration: 6000 }
    case 'network_error':
      return { message: '🌐 Cannot reach the server. Check your internet connection.', duration: 8000 }
    default:
      return { message: err.message || 'Something went wrong. Please try again.', duration: 5000 }
  }
}

export default function App() {
  const queryClient = useQueryClient()
  const [sessionId, setSessionId] = useState<string>('default')
  const [messages, setMessages] = useState<Message[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const streamingContentRef = useRef('')

  // Load messages for the current session
  const { data: loadedMessages } = useQuery({
    queryKey: ['messages', sessionId],
    queryFn: () => getMessages(sessionId),
    staleTime: 0,
  })

  useEffect(() => {
    if (loadedMessages) {
      setMessages(loadedMessages)
    }
  }, [loadedMessages])

  // Reset messages when switching sessions
  const handleSelectSession = (newSessionId: string) => {
    setSessionId(newSessionId)
    setMessages([]) // Clear immediately, useQuery will reload
  }

  const handleNewSession = () => {
    const newId = crypto.randomUUID()
    setSessionId(newId)
    setMessages([])
  }

  const [theme, setTheme] = useState<'light' | 'dark'>('light')

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  const handleClearChat = async () => {
    await clearMessages(sessionId)
    setMessages([])
    queryClient.invalidateQueries({ queryKey: ['messages', sessionId] })
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }

  const handleSessionDeleted = (deletedSessionId: string) => {
    if (deletedSessionId === sessionId) {
      handleNewSession()
    }
  }

  const handleSendMessage = useCallback(async (content: string) => {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }

    // Create a placeholder assistant message for streaming
    const assistantId = crypto.randomUUID()
    const assistantMessage: Message = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
    }

    setMessages((prev) => [...prev, userMessage, assistantMessage])
    setIsStreaming(true)
    streamingContentRef.current = ''

    let streamSources: Source[] = []

    try {
      await sendMessageStream(
        userMessage.id,
        content,
        messages,
        sessionId,
        {
          onToken: (token) => {
            streamingContentRef.current += token
            const currentContent = streamingContentRef.current
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, content: currentContent }
                  : msg,
              ),
            )
          },
          onMeta: (meta) => {
            streamSources = meta.sources
            if (meta.no_context) {
              toast('No relevant policy documents found for this question. The response is based on general knowledge.', {
                icon: 'ℹ️',
                duration: 5000,
              })
            }
          },
          onDone: (data) => {
            // Update the assistant message with final ID and sources
            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId
                  ? { ...msg, id: data.id, sources: streamSources }
                  : msg,
              ),
            )
            if (data.warning) {
              toast(data.warning, { icon: '⚠️', duration: 5000 })
            }
            queryClient.invalidateQueries({ queryKey: ['messages', sessionId] })
            queryClient.invalidateQueries({ queryKey: ['sessions'] })
          },
          onError: (error) => {
            // Remove the empty assistant message on error
            setMessages((prev) => prev.filter((msg) => msg.id !== assistantId))
            toast.error(error, { duration: 6000 })
          },
        },
      )
    } catch (err: any) {
      setMessages((prev) => prev.filter((msg) => msg.id !== assistantId))
      const errorMsg: ErrorResponse = {
        error_code: 'network_error',
        message: err?.message || 'Failed to connect to server',
      }
      const { message, duration } = getErrorToast(errorMsg)
      toast.error(message, { duration })
    } finally {
      setIsStreaming(false)
    }
  }, [messages, sessionId, queryClient])

  return (
    <div className="app-container">
      <Toaster position="bottom-right" />
      <SessionSidebar
        currentSessionId={sessionId}
        onSelectSession={handleSelectSession}
        onNewSession={handleNewSession}
        onSessionDeleted={handleSessionDeleted}
      />
      <div className="chat-container">
        <div className="chat-header">
          <h1>MemAI</h1>
          <button
            onClick={() =>
              setTheme((prev) => (prev === 'light' ? 'dark' : 'light'))
            }
            className="theme-toggle"
          >
            {theme === 'light' ? 'Dark' : 'Light'}
          </button>
          <button
            onClick={handleClearChat}
            className="clear-button"
            disabled={isStreaming}
          >
            Clear Chat
          </button>
        </div>

        <div className="messages-container">
          {messages.length === 0 ? (
            <div className="empty-state">
              <p>Ask me about NZ school property management policies!</p>
            </div>
          ) : (
            messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))
          )}
          {isStreaming && messages[messages.length - 1]?.content === '' && (
            <div className="loading-indicator">
              <div className="loading-dots">
                <span />
                <span />
                <span />
              </div>
              <span>AI is thinking...</span>
            </div>
          )}
        </div>

        <ChatInput
          onSendMessage={handleSendMessage}
          disabled={isStreaming}
        />
      </div>
    </div>
  )
}
