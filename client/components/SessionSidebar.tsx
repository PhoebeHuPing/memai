import { useQuery } from '@tanstack/react-query'
import { getSessions, SessionInfo } from '../apiClient'

interface SessionSidebarProps {
  currentSessionId: string
  onSelectSession: (sessionId: string) => void
  onNewSession: () => void
}

export default function SessionSidebar({
  currentSessionId,
  onSelectSession,
  onNewSession,
}: SessionSidebarProps) {
  const { data: sessions = [] } = useQuery({
    queryKey: ['sessions'],
    queryFn: getSessions,
    refetchInterval: 30000, // Refresh every 30s
  })

  const formatTime = (timestamp: number) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays === 1) {
      return 'Yesterday'
    } else if (diffDays < 7) {
      return `${diffDays} days ago`
    } else {
      return date.toLocaleDateString()
    }
  }

  return (
    <div className="session-sidebar">
      <div className="sidebar-header">
        <h2>Chats</h2>
        <button
          className="new-session-button"
          onClick={onNewSession}
          aria-label="New chat"
        >
          + New
        </button>
      </div>
      <ul className="session-list">
        {sessions.map((session: SessionInfo) => (
          <li
            key={session.session_id}
            className={`session-item ${session.session_id === currentSessionId ? 'active' : ''}`}
          >
            <button
              className="session-button"
              onClick={() => onSelectSession(session.session_id)}
            >
              <span className="session-title">{session.title}</span>
              <span className="session-time">{formatTime(session.last_active)}</span>
            </button>
          </li>
        ))}
        {sessions.length === 0 && (
          <li className="session-empty">No conversations yet</li>
        )}
      </ul>
    </div>
  )
}
