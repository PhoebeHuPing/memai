import { useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import { Message } from '../../types/Message'
import { sendMessage, getMessages, clearMessages } from '../apiClient'

const SESSION_ID = 'default' // Default session - can be extended for multiple sessions

export default function App() {
  const queryClient = useQueryClient()
  const [messages, setMessages] = useState<Message[]>([])

  // Load messages from backend on mount
  const { data: loadedMessages, isLoading } = useQuery({
    queryKey: ['messages', SESSION_ID],
    queryFn: () => getMessages(SESSION_ID),
    staleTime: 0, // Always fetch fresh data
  })

  useEffect(() => {
    if (loadedMessages) {
      setMessages(loadedMessages)
    }
  }, [loadedMessages])

  const mutation = useMutation({
    mutationFn: (content: string) => {
      const messageId = crypto.randomUUID()
      return sendMessage(messageId, content, messages, SESSION_ID)
    },
    onSuccess: (data) => {
      const newMessage: Message = {
        id: data.id,
        role: 'assistant',
        content: data.reply,
        timestamp: Date.now(),
        sources: data.sources,
      }
      setMessages((prev) => [...prev, newMessage])
      // Refetch to ensure sync with backend
      queryClient.invalidateQueries({ queryKey: ['messages', SESSION_ID] })
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
    await clearMessages(SESSION_ID)
    setMessages([])
    queryClient.invalidateQueries({ queryKey: ['messages', SESSION_ID] })
  }

  return (
    <div className="app-container">
      <div className="chat-container">
        <div className="chat-header">
          <h1>MemAI</h1>
          <button onClick={handleClearChat} className="clear-button" disabled={mutation.isPending}>
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
  )
}
