import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../../client/components/App'

// Mock API client
vi.mock('../apiClient', () => ({
  sendMessage: vi.fn(),
  getMessages: vi.fn(),
  clearMessages: vi.fn(),
}))

describe('App Component Integration', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })
  })

  const renderApp = () => {
    return render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    )
  }

  it('should render the app with initial empty state', async () => {
    const { getMessages } = await import('../apiClient')
    vi.mocked(getMessages).mockResolvedValue([])

    renderApp()

    expect(screen.getByText('MemAI')).toBeTruthy()
    expect(screen.getByText(/Ask me about/)).toBeTruthy()
  })

  it('should load messages from backend on mount', async () => {
    const { getMessages } = await import('../apiClient')
    const mockMessages = [
      {
        id: 'msg-1',
        role: 'user',
        content: 'Previous question',
        timestamp: 1000,
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content: 'Previous answer',
        timestamp: 2000,
        sources: [{ file: 'policy.pdf', page: '1', score: 0.95 }],
      },
    ]

    vi.mocked(getMessages).mockResolvedValue(mockMessages)

    renderApp()

    await waitFor(() => {
      expect(screen.getByText('Previous question')).toBeTruthy()
      expect(screen.getByText('Previous answer')).toBeTruthy()
    })
  })

  it('should send message and display response with sources', async () => {
    const { getMessages, sendMessage } = await import('../apiClient')

    vi.mocked(getMessages).mockResolvedValue([])
    vi.mocked(sendMessage).mockResolvedValue({
      id: 'msg-3',
      reply: 'Based on MOE policy...',
      sources: [{ file: 'handbook.pdf', page: '5', score: 0.92 }],
    })

    renderApp()

    const input = screen.getByPlaceholderText(/Type your message/)
    const sendButton = screen.getByRole('button', { name: /Send/ })

    await userEvent.type(input, 'What is the 5YA framework?')
    fireEvent.click(sendButton)

    await waitFor(() => {
      expect(screen.getByText('What is the 5YA framework?')).toBeTruthy()
      expect(screen.getByText(/Based on MOE policy/)).toBeTruthy()
      expect(screen.getByText(/handbook.pdf/)).toBeTruthy()
    })
  })

  it('should maintain separate message sessions', async () => {
    const { getMessages, sendMessage, clearMessages } =
      await import('../apiClient')

    vi.mocked(getMessages).mockResolvedValue([])
    vi.mocked(sendMessage).mockResolvedValue({
      id: 'msg-4',
      reply: 'Response',
      sources: [],
    })
    vi.mocked(clearMessages).mockResolvedValue({ status: 'ok' })

    renderApp()

    // Send a message
    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'First message')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    await waitFor(() => {
      expect(screen.getByText('First message')).toBeTruthy()
    })

    // Clear chat
    const clearButton = screen.getByRole('button', { name: /Clear Chat/ })
    fireEvent.click(clearButton)

    await waitFor(() => {
      expect(vi.mocked(clearMessages)).toHaveBeenCalled()
    })
  })

  it('should display loading indicator while sending message', async () => {
    const { getMessages, sendMessage } = await import('../apiClient')

    vi.mocked(getMessages).mockResolvedValue([])

    // Delay the response to see loading state
    vi.mocked(sendMessage).mockImplementation(
      () =>
        new Promise((resolve) =>
          setTimeout(
            () =>
              resolve({
                id: 'msg-5',
                reply: 'Response',
                sources: [],
              }),
            100,
          ),
        ),
    )

    renderApp()

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'Test message')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    // Should show loading indicator
    await waitFor(() => {
      expect(screen.getByText(/AI is thinking/)).toBeTruthy()
    })
  })

  it('should handle message with multiple sources correctly', async () => {
    const { getMessages, sendMessage } = await import('../apiClient')

    vi.mocked(getMessages).mockResolvedValue([])
    vi.mocked(sendMessage).mockResolvedValue({
      id: 'msg-6',
      reply: 'Based on multiple policies...',
      sources: [
        { file: 'policy1.pdf', page: '1', score: 0.95 },
        { file: 'policy2.pdf', page: '3', score: 0.88 },
        { file: 'guide.pdf', page: '10', score: 0.82 },
      ],
    })

    renderApp()

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'Complex question')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    await waitFor(() => {
      expect(screen.getByText(/policy1.pdf/)).toBeTruthy()
      expect(screen.getByText(/policy2.pdf/)).toBeTruthy()
      expect(screen.getByText(/guide.pdf/)).toBeTruthy()
    })
  })

  it('should refetch messages after successful send', async () => {
    const { getMessages, sendMessage } = await import('../apiClient')

    vi.mocked(getMessages)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([
        {
          id: 'msg-7',
          role: 'user',
          content: 'New question',
          timestamp: Date.now(),
        },
        {
          id: 'msg-8',
          role: 'assistant',
          content: 'New answer',
          timestamp: Date.now(),
          sources: [],
        },
      ])

    vi.mocked(sendMessage).mockResolvedValue({
      id: 'msg-8',
      reply: 'New answer',
      sources: [],
    })

    renderApp()

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'New question')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    await waitFor(() => {
      expect(vi.mocked(getMessages)).toHaveBeenCalledTimes(2)
    })
  })
})
