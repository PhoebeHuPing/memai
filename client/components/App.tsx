import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import toast, { Toaster } from 'react-hot-toast'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import SessionSidebar from './SessionSidebar'
import { Message } from '../../types/Message'
import {
  sendMessageStream,
  getMessages,
  clearMessages,
  getSessions,
} from '../apiClient'

export default function App() {
  const queryClient = useQueryClient()
  const [currentSessionId, setCurrentSessionId] = useState('default')
  const [messages, setMessages] = useState<Message[]>([])

  const { data: loadedMessages, isLoading } = useQuery({
    queryKey: ['messages', currentSessionId],
    queryFn: () => getMessages(currentSessionId),
    staleTime: 0,
  })

  const { data: sessions = [] } = useQuery({
    queryKey: ['sessions'],
    queryFn: getSessions,
    refetchInterval: 30000,
  })

  useEffect(() => {
    if (loadedMessages !== undefined) {
      setMessages(loadedMessages)
    }
  }, [currentSessionId, loadedMessages])

  const mutation = useMutation({
    mutationFn: async (content: string) => {
      const messageId = crypto.randomUUID()
      const assistantId = `assistant-${crypto.randomUUID()}`

      await new Promise<void>((resolve, reject) => {
        sendMessageStream(messageId, content, messages, currentSessionId, {
          onToken: (token) => {
            setMessages((prev) => {
              const lastMessage = prev[prev.length - 1]

              if (
                lastMessage &&
                lastMessage.role === 'assistant' &&
                lastMessage.id === assistantId
              ) {
                return prev.map((msg) =>
                  msg.id === assistantId
                    ? { ...msg, content: `${msg.content}${token}` }
                    : msg,
                )
              }

              return [
                ...prev,
                {
                  id: assistantId,
                  role: 'assistant',
                  content: token,
                  timestamp: Date.now(),
                  sources: [],
                },
              ]
            })
          },
          onMeta: ({ sources, no_context }) => {
            if (no_context) {
              toast(
                'No relevant policy documents found for this question. The response is based on general knowledge.',
                {
                  icon: 'ℹ️',
                },
              )
            }

            setMessages((prev) =>
              prev.map((msg) =>
                msg.id === assistantId ? { ...msg, sources } : msg,
              ),
            )
          },
          onDone: ({ warning }) => {
            if (warning) {
              toast.warning(warning)
            }
            resolve()
          },
          onError: (error) => {
            toast.error(error)
            reject(new Error(error))
          },
        })
      })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ['messages', currentSessionId],
      })
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
    },
    onError: () => {
      queryClient.invalidateQueries({
        queryKey: ['messages', currentSessionId],
      })
    },
  })

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

  const handleClearChat = async () => {
    await clearMessages(currentSessionId)
    setMessages([])
    queryClient.invalidateQueries({ queryKey: ['messages', currentSessionId] })
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }

  const handleSelectSession = (sessionId: string) => {
    setCurrentSessionId(sessionId)
    setMessages([])
  }

  const handleNewSession = () => {
    const sessionId = crypto.randomUUID()
    setCurrentSessionId(sessionId)
    setMessages([])
  }

  const handleSessionDeleted = (
    deletedSessionId: string,
    nextSessionId?: string,
  ) => {
    if (deletedSessionId === currentSessionId) {
      const fallbackSessionId = nextSessionId || 'default'

      setCurrentSessionId(fallbackSessionId)
      setMessages([])
      queryClient.removeQueries({ queryKey: ['messages', deletedSessionId] })
      queryClient.invalidateQueries({
        queryKey: ['messages', fallbackSessionId],
      })
    } else {
      queryClient.invalidateQueries({
        queryKey: ['messages', currentSessionId],
      })
    }
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }

  return (
    <>
      <Toaster position="top-right" />
      <div className="app-container">
        <SessionSidebar
          currentSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onNewSession={handleNewSession}
          onSessionDeleted={handleSessionDeleted}
        />
        <div className="chat-container">
          <div className="chat-header">
            <h1>MemAI</h1>
            <span className="session-label">
              {sessions.find(
                (session) => session.session_id === currentSessionId,
              )?.title || 'Default chat'}
            </span>
            <button
              onClick={handleClearChat}
              className="clear-button"
              disabled={mutation.isPending}
            >
              Clear Chat
            </button>
          </div>

          <div className="messages-container">
            {isLoading ? (
              <div className="loading-indicator">
                <div className="loading-dots">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
                <span>Loading messages...</span>
              </div>
            ) : messages.length === 0 ? (
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
                  <span></span>
                  <span></span>
                  <span></span>
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
    </>
  )
}
