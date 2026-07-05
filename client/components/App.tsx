import { useState, useEffect } from 'react'
import toast, { Toaster } from 'react-hot-toast'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import SessionSidebar from './SessionSidebar'
import { Message } from '../../types/Message'
import {
  sendMessage,
  getMessages,
  clearMessages,
  parseApiError,
  ChatResponse,
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

  const mutation = useMutation({
    mutationFn: (content: string) => {
      const messageId = crypto.randomUUID()
      return sendMessage(messageId, content, messages, sessionId)
    },
    onError: (error: any) => {
      toast.dismiss()
      const parsed = parseApiError(error)
      const { message, duration } = getErrorToast(parsed)
      toast.error(message, { duration })
    },
    onSuccess: (data: ChatResponse) => {
      toast.dismiss()

      // Show warning if DB persistence failed
      if (data.warning) {
        toast(data.warning, { icon: '⚠️', duration: 5000 })
      }

      // Show notice if no relevant documents were found
      if (data.no_context) {
        toast('No relevant policy documents found for this question. The response is based on general knowledge.', {
          icon: 'ℹ️',
          duration: 5000,
        })
      }

      const newMessage: Message = {
        id: data.id,
        role: 'assistant',
        content: data.reply,
        timestamp: Date.now(),
        sources: data.sources,
      }
      setMessages((prev) => [...prev, newMessage])
      queryClient.invalidateQueries({ queryKey: ['messages', sessionId] })
      // Refresh session list so the new session appears
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
  })

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
      // Deleted the current session — switch to a new one
      handleNewSession()
    }
  }

  const handleSendMessage = (content: string) => {
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    setMessages((prev) => [...prev, userMessage])
    mutation.mutate(content)
  }

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
            disabled={mutation.isPending}
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
          {mutation.isPending && (
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
          disabled={mutation.isPending}
        />
      </div>
    </div>
  )
}
