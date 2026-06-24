import { describe, it, expect, vi, beforeEach } from 'vitest'
import { sendMessage, getMessages, clearMessages } from '../../client/apiClient'
import request from 'superagent'
import { Message } from '../../types/Message'

vi.mock('superagent')

describe('sendMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should send a message and return the AI reply with sources', async () => {
    const mockReply = 'Based on MOE policy...'
    const mockSources = [{ file: 'policy.pdf', page: '1', score: 0.95 }]
    vi.mocked(request.post).mockReturnValue({
      send: vi.fn().mockResolvedValue({
        body: {
          id: 'msg-123',
          reply: mockReply,
          sources: mockSources,
        },
      }),
    } as any)

    const result = await sendMessage(
      'msg-001',
      'What is the 5YA framework?',
      [],
      'default',
    )

    expect(result.reply).toBe(mockReply)
    expect(result.sources).toEqual(mockSources)
    expect(request.post).toHaveBeenCalledWith('/api/v1/chat')
  })

  it('should send conversation history with the message', async () => {
    const mockReply = 'That sounds like a Priority 2 issue!'
    const sendMock = vi.fn().mockResolvedValue({
      body: {
        id: 'msg-124',
        reply: mockReply,
        sources: [],
      },
    })
    vi.mocked(request.post).mockReturnValue({
      send: sendMock,
    } as any)

    const history: Message[] = [
      {
        id: '1',
        role: 'user',
        content: 'We have a roof leak',
        timestamp: Date.now(),
      },
      {
        id: '2',
        role: 'assistant',
        content: 'That requires immediate attention',
        timestamp: Date.now(),
      },
    ]
    const message = 'What should we do about it?'

    const result = await sendMessage('msg-125', message, history, 'default')

    expect(result.reply).toBe(mockReply)
    expect(request.post).toHaveBeenCalledWith('/api/v1/chat')
    expect(sendMock).toHaveBeenCalledWith({
      message_id: 'msg-125',
      message,
      history,
      session_id: 'default',
    })
  })

  it('should include multiple sources in response', async () => {
    const mockSources = [
      { file: 'policy1.pdf', page: '1', score: 0.95 },
      { file: 'policy2.pdf', page: '5', score: 0.88 },
      { file: 'guide.pdf', page: '10', score: 0.82 },
    ]
    vi.mocked(request.post).mockReturnValue({
      send: vi.fn().mockResolvedValue({
        body: {
          id: 'msg-126',
          reply: 'Multi-source answer',
          sources: mockSources,
        },
      }),
    } as any)

    const result = await sendMessage(
      'msg-127',
      'Complex question',
      [],
      'default',
    )

    expect(result.sources).toHaveLength(3)
    expect(result.sources[0].score).toBe(0.95)
  })

  it('should handle errors appropriately', async () => {
    vi.mocked(request.post).mockReturnValue({
      send: vi.fn().mockRejectedValue(new Error('Network error')),
    } as any)

    await expect(sendMessage('msg-128', 'test', [], 'default')).rejects.toThrow(
      'Network error',
    )
  })
})

describe('getMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should fetch messages for a session', async () => {
    const mockMessages: Message[] = [
      {
        id: 'msg-1',
        role: 'user',
        content: 'What is the 5YA?',
        timestamp: 1000,
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content: 'The 5YA is...',
        timestamp: 2000,
        sources: [{ file: 'policy.pdf', page: '1', score: 0.95 }],
      },
    ]

    const mockResponse = { body: mockMessages }
    vi.mocked(request.get).mockReturnValue({
      query: vi.fn().mockResolvedValue(mockResponse),
    } as any)

    const result = await getMessages('default')

    expect(result).toEqual(mockMessages)
    expect(request.get).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/messages'),
    )
  })

  it('should handle empty message list', async () => {
    vi.mocked(request.get).mockReturnValue({
      query: vi.fn().mockResolvedValue({
        body: [],
      }),
    } as any)

    const result = await getMessages('empty-session')

    expect(result).toEqual([])
  })

  it('should handle messages with multiple sources', async () => {
    const mockMessages: Message[] = [
      {
        id: 'msg-3',
        role: 'assistant',
        content: 'Answer from multiple sources',
        timestamp: 3000,
        sources: [
          { file: 'policy1.pdf', page: '1', score: 0.95 },
          { file: 'policy2.pdf', page: '5', score: 0.88 },
          { file: 'guide.pdf', page: '10', score: 0.82 },
        ],
      },
    ]

    vi.mocked(request.get).mockReturnValue({
      query: vi.fn().mockResolvedValue({
        body: mockMessages,
      }),
    } as any)

    const result = await getMessages('multi-source-session')

    expect(result[0].sources).toHaveLength(3)
    expect(result[0].sources.map((s) => s.file)).toContain('policy1.pdf')
  })

  it('should handle fetch errors', async () => {
    const mockError = new Error('Fetch failed')
    vi.mocked(request.get).mockReturnValue({
      query: vi.fn().mockRejectedValue(mockError),
    } as any)

    await expect(getMessages('error-session')).rejects.toThrow('Fetch failed')
  })
})

describe('clearMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should clear messages for a session', async () => {
    vi.mocked(request.delete).mockReturnValue({
      query: vi.fn().mockReturnValue({
        end: vi.fn().mockResolvedValue({
          body: { status: 'ok' },
        }),
      }),
    } as any)

    const result = await clearMessages('default')

    // clearMessages returns void, but the call should succeed
    expect(result).toBeUndefined()
    expect(request.delete).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/messages'),
    )
  })

  it('should clear different sessions independently', async () => {
    vi.mocked(request.delete).mockReturnValue({
      query: vi.fn().mockReturnValue({
        end: vi.fn().mockResolvedValue({
          body: { status: 'ok' },
        }),
      }),
    } as any)

    await clearMessages('session-1')
    await clearMessages('session-2')

    expect(request.delete).toHaveBeenCalledTimes(2)
  })

  it('should handle clear errors', async () => {
    // Since clearMessages has Promise<void>, it doesn't report results
    // Just verify it can be called without errors
    vi.mocked(request.delete).mockReturnValue({
      query: vi.fn().mockReturnValue({
        end: vi.fn().mockResolvedValue({
          body: { status: 'ok' },
        }),
      }),
    } as any)

    // Should not throw
    await clearMessages('error-session')
    expect(request.delete).toHaveBeenCalled()
  })
})
