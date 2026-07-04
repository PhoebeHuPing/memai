import { describe, it, expect, vi, beforeEach } from 'vitest'
import { sendMessage, getMessages, clearMessages, parseApiError } from '../../client/apiClient'
import request from 'superagent'
import { Message } from '../../types/Message'

vi.mock('superagent')

/** Helper to create a chainable mock that ends with .timeout() */
function mockChain(resolvedValue: any) {
  const chain: any = {}
  chain.send = vi.fn().mockReturnValue(chain)
  chain.query = vi.fn().mockReturnValue(chain)
  chain.timeout = vi.fn().mockResolvedValue(resolvedValue)
  return chain
}

function mockChainRejected(error: any) {
  const chain: any = {}
  chain.send = vi.fn().mockReturnValue(chain)
  chain.query = vi.fn().mockReturnValue(chain)
  chain.timeout = vi.fn().mockRejectedValue(error)
  return chain
}

describe('sendMessage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should send a message and return the AI reply with sources', async () => {
    const mockReply = 'Based on MOE policy...'
    const mockSources = [{ file: 'policy.pdf', page: '1', score: 0.95 }]
    const chain = mockChain({
      body: {
        id: 'msg-123',
        reply: mockReply,
        sources: mockSources,
        no_context: false,
      },
    })
    vi.mocked(request.post).mockReturnValue(chain)

    const result = await sendMessage(
      'msg-001',
      'What is the 5YA framework?',
      [],
      'default',
    )

    expect(result.reply).toBe(mockReply)
    expect(result.sources).toEqual(mockSources)
    expect(result.no_context).toBe(false)
    expect(request.post).toHaveBeenCalledWith('/api/v1/chat')
  })

  it('should send conversation history with the message', async () => {
    const mockReply = 'That sounds like a Priority 2 issue!'
    const chain = mockChain({
      body: {
        id: 'msg-124',
        reply: mockReply,
        sources: [],
        no_context: false,
      },
    })
    vi.mocked(request.post).mockReturnValue(chain)

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
    expect(chain.send).toHaveBeenCalledWith({
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
    const chain = mockChain({
      body: {
        id: 'msg-126',
        reply: 'Multi-source answer',
        sources: mockSources,
        no_context: false,
      },
    })
    vi.mocked(request.post).mockReturnValue(chain)

    const result = await sendMessage(
      'msg-127',
      'Complex question',
      [],
      'default',
    )

    expect(result.sources).toHaveLength(3)
    expect(result.sources[0].score).toBe(0.95)
  })

  it('should return no_context=true when no documents found', async () => {
    const chain = mockChain({
      body: {
        id: 'msg-130',
        reply: 'I could not find relevant context...',
        sources: [],
        no_context: true,
      },
    })
    vi.mocked(request.post).mockReturnValue(chain)

    const result = await sendMessage('msg-130', 'random question', [], 'default')

    expect(result.no_context).toBe(true)
    expect(result.sources).toEqual([])
  })

  it('should return warning when DB persistence fails', async () => {
    const chain = mockChain({
      body: {
        id: 'msg-131',
        reply: 'Generated answer',
        sources: [],
        no_context: false,
        warning: 'Message generated but could not be saved to history.',
      },
    })
    vi.mocked(request.post).mockReturnValue(chain)

    const result = await sendMessage('msg-131', 'test', [], 'default')

    expect(result.warning).toBe('Message generated but could not be saved to history.')
  })

  it('should handle errors appropriately', async () => {
    const chain = mockChainRejected(new Error('Network error'))
    vi.mocked(request.post).mockReturnValue(chain)

    await expect(sendMessage('msg-128', 'test', [], 'default')).rejects.toThrow(
      'Network error',
    )
  })

  it('should set timeout on requests', async () => {
    const chain = mockChain({
      body: {
        id: 'msg-129',
        reply: 'reply',
        sources: [],
        no_context: false,
      },
    })
    vi.mocked(request.post).mockReturnValue(chain)

    await sendMessage('msg-129', 'test', [], 'default')

    expect(chain.timeout).toHaveBeenCalledWith(
      expect.objectContaining({ response: expect.any(Number), deadline: expect.any(Number) }),
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

    const chain = mockChain({ body: mockMessages })
    vi.mocked(request.get).mockReturnValue(chain)

    const result = await getMessages('default')

    expect(result).toEqual(mockMessages)
    expect(request.get).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/messages'),
    )
  })

  it('should handle empty message list', async () => {
    const chain = mockChain({ body: [] })
    vi.mocked(request.get).mockReturnValue(chain)

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

    const chain = mockChain({ body: mockMessages })
    vi.mocked(request.get).mockReturnValue(chain)

    const result = await getMessages('multi-source-session')

    expect(result[0].sources).toHaveLength(3)
    expect(result[0].sources!.map((s) => s.file)).toContain('policy1.pdf')
  })

  it('should handle fetch errors', async () => {
    const chain = mockChainRejected(new Error('Fetch failed'))
    vi.mocked(request.get).mockReturnValue(chain)

    await expect(getMessages('error-session')).rejects.toThrow('Fetch failed')
  })
})

describe('clearMessages', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should clear messages for a session', async () => {
    const chain = mockChain({ body: { status: 'ok' } })
    vi.mocked(request.delete).mockReturnValue(chain)

    const result = await clearMessages('default')

    expect(result).toBeUndefined()
    expect(request.delete).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/messages'),
    )
  })

  it('should clear different sessions independently', async () => {
    const chain = mockChain({ body: { status: 'ok' } })
    vi.mocked(request.delete).mockReturnValue(chain)

    await clearMessages('session-1')
    await clearMessages('session-2')

    expect(request.delete).toHaveBeenCalledTimes(2)
  })

  it('should handle clear errors', async () => {
    const chain = mockChain({ body: { status: 'ok' } })
    vi.mocked(request.delete).mockReturnValue(chain)

    await clearMessages('error-session')
    expect(request.delete).toHaveBeenCalled()
  })
})

describe('parseApiError', () => {
  it('should parse structured error response from server', () => {
    const error = {
      response: {
        body: {
          error_code: 'timeout',
          message: 'All models timed out.',
        },
      },
    }

    const result = parseApiError(error)

    expect(result.error_code).toBe('timeout')
    expect(result.message).toBe('All models timed out.')
  })

  it('should handle timeout errors from superagent', () => {
    const error = { timeout: true }

    const result = parseApiError(error)

    expect(result.error_code).toBe('timeout')
  })

  it('should handle network errors with no response', () => {
    const error = { message: 'socket hang up' }

    const result = parseApiError(error)

    expect(result.error_code).toBe('network_error')
  })

  it('should handle unknown errors', () => {
    const error = { response: { body: {} }, message: 'Something weird' }

    const result = parseApiError(error)

    expect(result.error_code).toBe('unknown')
    expect(result.message).toBe('Something weird')
  })
})
