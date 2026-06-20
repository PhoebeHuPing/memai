import { useState, useEffect } from 'react'
import { useMutation } from '@tanstack/react-query'
import ChatMessage from './ChatMessage'
import ChatInput from './ChatInput'
import { Message } from '../../types/Message'
import { sendMessage } from '../apiClient'

export default function App() {
  const [messages, setMessages] = useState<Message[]>([])
  useEffect(() => {
    const stored = localStorage.getItem('memai_messages');
    if (stored) {
      try {
        setMessages(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse stored messages', e);
      }
    }
  }, []);

  // Save whenever messages change
  useEffect(() => {
    localStorage.setItem('memai_messages', JSON.stringify(messages));
  }, [messages]);
  const mutation = useMutation({
    mutationFn: (content: string) => sendMessage(content, messages),
    onSuccess: (data) => {
      const newMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: data.reply,
        timestamp: Date.now(),
        sources: data.sources,
      }
      setMessages((prev) => [...prev, newMessage])
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

  const handleClearChat = () => setMessages([])

  return (
    <div className="app-container">
      <div className="chat-container">
        <div className="chat-header">
          <h1>MemAI</h1>
          <button onClick={handleClearChat} className="clear-button">
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
