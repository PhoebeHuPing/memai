import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getSessions, renameSession, deleteSession, SessionInfo } from '../apiClient'

interface SessionSidebarProps {
  currentSessionId: string
  onSelectSession: (sessionId: string) => void
  onNewSession: () => void
  onSessionDeleted: (deletedSessionId: string) => void
}

export default function SessionSidebar({
  currentSessionId,
  onSelectSession,
  onNewSession,
  onSessionDeleted,
}: SessionSidebarProps) {
  const queryClient = useQueryClient()
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editTitle, setEditTitle] = useState('')

  const { data: sessions = [] } = useQuery({
    queryKey: ['sessions'],
    queryFn: getSessions,
    refetchInterval: 30000,
  })

  const renameMutation = useMutation({
    mutationFn: ({ sessionId, title }: { sessionId: string; title: string }) =>
      renameSession(sessionId, title),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      setEditingId(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (sessionId: string) => deleteSession(sessionId),
    onSuccess: (_, sessionId) => {
      queryClient.invalidateQueries({ queryKey: ['sessions'] })
      onSessionDeleted(sessionId)
    },
  })

  const handleStartRename = (session: SessionInfo) => {
    setEditingId(session.session_id)
    setEditTitle(session.title)
  }

  const handleConfirmRename = () => {
    if (editingId && editTitle.trim()) {
      renameMutation.mutate({ sessionId: editingId, title: editTitle.trim() })
    } else {
      setEditingId(null)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleConfirmRename()
    } else if (e.key === 'Escape') {
      setEditingId(null)
    }
  }

  const handleDelete = (sessionId: string) => {
    if (window.confirm('Delete this conversation? This cannot be undone.')) {
      deleteMutation.mutate(sessionId)
    }
  }

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
            {editingId === session.session_id ? (
              <div className="session-edit">
                <input
                  className="session-edit-input"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onBlur={handleConfirmRename}
                  autoFocus
                  maxLength={60}
                />
              </div>
            ) : (
              <div className="session-row">
                <button
                  className="session-button"
                  onClick={() => onSelectSession(session.session_id)}
                >
                  <span className="session-title">{session.title}</span>
                  <span className="session-time">{formatTime(session.last_active)}</span>
                </button>
                <div className="session-actions">
                  <button
                    className="session-action-btn"
                    onClick={() => handleStartRename(session)}
                    aria-label="Rename conversation"
                    title="Rename"
                  >
                    ✏️
                  </button>
                  <button
                    className="session-action-btn session-action-delete"
                    onClick={() => handleDelete(session.session_id)}
                    aria-label="Delete conversation"
                    title="Delete"
                  >
                    🗑️
                  </button>
                </div>
              </div>
            )}
          </li>
        ))}
        {sessions.length === 0 && (
          <li className="session-empty">No conversations yet</li>
        )}
      </ul>
    </div>
  )
}
