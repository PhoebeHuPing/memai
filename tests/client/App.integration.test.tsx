import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from '../../client/components/App'
import * as apiClient from '../../client/apiClient'

// jsdom doesn't implement matchMedia — react-hot-toast needs it
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock API client
vi.mock('../../client/apiClient', () => ({
  sendMessageStream: vi.fn(),
  getMessages: vi.fn(),
  clearMessages: vi.fn(),
  getSessions: vi.fn().mockResolvedValue([]),
  renameSession: vi.fn(),
  deleteSession: vi.fn(),
  parseApiError: vi.fn().mockReturnValue({ error_code: 'unknown', message: 'Error' }),
}))

const mockGetMessages = vi.mocked(apiClient.getMessages)
const mockSendMessageStream = vi.mocked(apiClient.sendMessageStream)
const mockClearMessages = vi.mocked(apiClient.clearMessages)

/**
 * Helper to configure sendMessageStream to immediately invoke callbacks.
 */
function setupStreamMock(response: {
  id: string
  reply: string
  sources: Array<{ file: string; page: string; score: number }>
  no_context: boolean
  warning?: string
}) {
  mockSendMessageStream.mockImplementation(
    async (_messageId, _message, _history, _sessionId, callbacks) => {
      callbacks.onMeta?.({ sources: response.sources, no_context: response.no_context })
      // Stream the reply as a single token
      callbacks.onToken(response.reply)
      callbacks.onDone({ id: response.id, warning: response.warning })
    },
  )
}

describe('App Component Integration', () => {
  let queryClient: QueryClient

  beforeEach(() => {
    vi.clearAllMocks()
    cleanup()
    queryClient = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
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
    mockGetMessages.mockResolvedValue([])

    renderApp()

    expect(screen.getByText('MemAI')).toBeTruthy()
    expect(screen.getByText(/Ask me about/)).toBeTruthy()
  })

  it('should load messages from backend on mount', async () => {
    const mockMessages = [
      {
        id: 'msg-1',
        role: 'user' as const,
        content: 'Previous question',
        timestamp: 1000,
      },
      {
        id: 'msg-2',
        role: 'assistant' as const,
        content: 'Previous answer',
        timestamp: 2000,
        sources: [{ file: 'policy.pdf', page: '1', score: 0.95 }],
      },
    ]

    mockGetMessages.mockResolvedValue(mockMessages)

    renderApp()

    await waitFor(() => {
      expect(screen.getByText('Previous question')).toBeTruthy()
      expect(screen.getByText('Previous answer')).toBeTruthy()
    })
  })

  it('should send message and display streamed response', async () => {
    mockGetMessages.mockResolvedValue([])
    setupStreamMock({
      id: 'msg-3',
      reply: 'Based on MOE policy...',
      sources: [{ file: 'handbook.pdf', page: '5', score: 0.92 }],
      no_context: false,
    })

    renderApp()

    await waitFor(() => {
      expect(screen.getByText(/Ask me about/)).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/Type your message/)
    const sendButton = screen.getByRole('button', { name: /Send/ })

    await userEvent.type(input, 'What is the 5YA framework?')
    fireEvent.click(sendButton)

    await waitFor(() => {
      expect(screen.getByText('What is the 5YA framework?')).toBeTruthy()
      expect(screen.getByText(/Based on MOE policy/)).toBeTruthy()
    })
  })

  it('should clear chat messages', async () => {
    mockGetMessages.mockResolvedValue([])
    mockClearMessages.mockResolvedValue(undefined)
    setupStreamMock({
      id: 'msg-4',
      reply: 'Response',
      sources: [],
      no_context: false,
    })

    renderApp()

    await waitFor(() => {
      expect(screen.getByText(/Ask me about/)).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'First message')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    await waitFor(() => {
      expect(screen.getByText('First message')).toBeTruthy()
    })

    fireEvent.click(screen.getByRole('button', { name: /Clear Chat/ }))

    await waitFor(() => {
      expect(mockClearMessages).toHaveBeenCalled()
    })
  })

  it('should display loading indicator while waiting for stream', async () => {
    mockGetMessages.mockResolvedValue([])
    // Simulate a slow stream that doesn't resolve immediately
    mockSendMessageStream.mockImplementation(
      async (_messageId, _message, _history, _sessionId, callbacks) => {
        callbacks.onMeta?.({ sources: [], no_context: false })
        // Delay before sending first token
        await new Promise((resolve) => setTimeout(resolve, 200))
        callbacks.onToken('Response')
        callbacks.onDone({ id: 'msg-5' })
      },
    )

    renderApp()

    await waitFor(() => {
      expect(screen.getByText(/Ask me about/)).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'Test message')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    // Should show loading indicator when assistant content is still empty
    await waitFor(() => {
      expect(screen.getByText(/AI is thinking/)).toBeTruthy()
    })
  })

  it('should handle multiple sources in streamed response', async () => {
    mockGetMessages.mockResolvedValue([])
    setupStreamMock({
      id: 'msg-6',
      reply: 'Based on multiple policies...',
      sources: [
        { file: 'policy1.pdf', page: '1', score: 0.95 },
        { file: 'policy2.pdf', page: '3', score: 0.88 },
        { file: 'guide.pdf', page: '10', score: 0.82 },
      ],
      no_context: false,
    })

    renderApp()

    await waitFor(() => {
      expect(screen.getByText(/Ask me about/)).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'Complex question')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    await waitFor(() => {
      expect(screen.getByText(/Based on multiple policies/)).toBeTruthy()
    })
  })

  it('should show no_context toast when response has no relevant documents', async () => {
    mockGetMessages.mockResolvedValue([])
    setupStreamMock({
      id: 'msg-toast-1',
      reply: 'General knowledge answer',
      sources: [],
      no_context: true,
    })

    renderApp()

    await waitFor(() => {
      expect(screen.getByText(/Ask me about/)).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'Something unrelated to policy')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    await waitFor(() => {
      expect(
        screen.getByText(
          'No relevant policy documents found for this question. The response is based on general knowledge.',
        ),
      ).toBeTruthy()
    })
  })

  it('should show warning toast when response includes a warning', async () => {
    mockGetMessages.mockResolvedValue([])
    setupStreamMock({
      id: 'msg-toast-2',
      reply: 'Partial answer with caveat',
      sources: [{ file: 'policy.pdf', page: '2', score: 0.7 }],
      no_context: false,
      warning: 'Some retrieved documents may be outdated.',
    })

    renderApp()

    await waitFor(() => {
      expect(screen.getByText(/Ask me about/)).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'Question with warning')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    await waitFor(() => {
      expect(
        screen.getByText('Some retrieved documents may be outdated.'),
      ).toBeTruthy()
    })
  })

  it('should handle stream errors gracefully', async () => {
    mockGetMessages.mockResolvedValue([])
    mockSendMessageStream.mockImplementation(
      async (_messageId, _message, _history, _sessionId, callbacks) => {
        callbacks.onError('Service unavailable')
      },
    )

    renderApp()

    await waitFor(() => {
      expect(screen.getByText(/Ask me about/)).toBeTruthy()
    })

    const input = screen.getByPlaceholderText(/Type your message/)
    await userEvent.type(input, 'Will fail')
    fireEvent.click(screen.getByRole('button', { name: /Send/ }))

    // The user message should appear
    await waitFor(() => {
      expect(screen.getByText('Will fail')).toBeTruthy()
    })
  })
})
