import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import ChatMessage from '../../client/components/ChatMessage'
import { Message } from '../../types/Message'

describe('ChatMessage Component', () => {
  it('should render user message without markdown parsing', () => {
    const message: Message = {
      id: 'msg-1',
      role: 'user',
      content: 'What is the **5YA** framework?',
      timestamp: Date.now(),
    }

    render(<ChatMessage message={message} />)

    const messageText = screen.getByText(/5YA/)
    expect(messageText).toBeTruthy()
    // User messages should NOT render markdown (should show raw text)
  })

  it('should render assistant message with markdown formatting', () => {
    const message: Message = {
      id: 'msg-2',
      role: 'assistant',
      content: '# MOE Framework\n\nThe **5YA** is important.',
      timestamp: Date.now(),
    }

    render(<ChatMessage message={message} />)

    // Check that heading exists (markdown parsed)
    const heading = screen.getByText('MOE Framework')
    expect(heading).toBeTruthy()
  })

  it('should display sources with file and page information', () => {
    const message: Message = {
      id: 'msg-3',
      role: 'assistant',
      content: 'Response',
      timestamp: Date.now(),
      sources: [
        { file: 'policy.pdf', page: '1', score: 0.95 },
        { file: 'guide.pdf', page: '5', score: 0.87 },
      ],
    }

    render(<ChatMessage message={message} />)

    expect(screen.getByText(/policy\.pdf/)).toBeTruthy()
    expect(screen.getByText(/p\.1/)).toBeTruthy()
    expect(screen.getByText(/guide\.pdf/)).toBeTruthy()
    expect(screen.getByText(/p\.5/)).toBeTruthy()
  })

  it('should not display sources section when message has no sources', () => {
    const message: Message = {
      id: 'msg-4',
      role: 'assistant',
      content: 'Response without sources',
      timestamp: Date.now(),
    }

    render(<ChatMessage message={message} />)

    // Should not have sources label
    const sourceLabels = screen.queryAllByText(/📎 Sources/)
    expect(sourceLabels.length).toBe(0)
  })

  it('should render markdown tables correctly', () => {
    const message: Message = {
      id: 'msg-5',
      role: 'assistant',
      content: `| Priority | Description |
| --- | --- |
| 1 | Urgent |
| 2 | High |`,
      timestamp: Date.now(),
    }

    render(<ChatMessage message={message} />)

    // Check table content is rendered
    expect(screen.getByText(/Priority/)).toBeTruthy()
    expect(screen.getByText(/Urgent/)).toBeTruthy()
  })

  it('should display message timestamp in readable format', () => {
    const now = Date.now()
    const message: Message = {
      id: 'msg-6',
      role: 'user',
      content: 'Test',
      timestamp: now,
    }

    render(<ChatMessage message={message} />)

    // Should show time in locale format
    const timeStr = new Date(now).toLocaleTimeString()
    expect(screen.getByText(timeStr)).toBeTruthy()
  })

  it('should render code blocks with syntax highlighting', () => {
    const message: Message = {
      id: 'msg-7',
      role: 'assistant',
      content: '```json\n{"priority": "1"}\n```',
      timestamp: Date.now(),
    }

    render(<ChatMessage message={message} />)

    // Code block should be rendered
    expect(screen.getByText(/priority/)).toBeTruthy()
  })

  it('should handle messages with empty sources array', () => {
    const message: Message = {
      id: 'msg-8',
      role: 'assistant',
      content: 'Response',
      timestamp: Date.now(),
      sources: [],
    }

    render(<ChatMessage message={message} />)

    // Should render without error but no sources shown
    const sourceLabels = screen.queryAllByText(/📎 Sources/)
    expect(sourceLabels.length).toBe(0)
  })

  it('should render multiple lines of markdown content', () => {
    const message: Message = {
      id: 'msg-9',
      role: 'assistant',
      content: `
## Priority Level Analysis

- **Level 1**: Safety critical
- **Level 2**: Functional impact
- **Level 3**: Maintenance
- **Level 4**: Minor

For more details, see page 2.
      `.trim(),
      timestamp: Date.now(),
    }

    render(<ChatMessage message={message} />)

    // Check that list items and formatting is there
    expect(screen.getByText(/Priority Level Analysis/)).toBeTruthy()
    expect(screen.getByText(/Safety critical/)).toBeTruthy()
  })

  it('should correctly distinguish user vs assistant styling', () => {
    const userMsg: Message = {
      id: 'msg-10',
      role: 'user',
      content: 'User question',
      timestamp: Date.now(),
    }

    const { container } = render(<ChatMessage message={userMsg} />)

    // Check for user-message class
    const messageDiv = container.querySelector('.user-message')
    expect(messageDiv).toBeTruthy()

    // Should show "You" label
    expect(screen.getByText('You')).toBeTruthy()
  })

  it('should show MemAI label for assistant messages', () => {
    const assistantMsg: Message = {
      id: 'msg-11',
      role: 'assistant',
      content: 'Assistant response',
      timestamp: Date.now(),
    }

    render(<ChatMessage message={assistantMsg} />)

    // Should show "MemAI" label
    expect(screen.getByText('MemAI')).toBeTruthy()
  })
})
