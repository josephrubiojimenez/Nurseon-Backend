import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import '../../Styles/PagesStyle/NurseonAIChat.css';
import { loadPersistedState, savePersistedState } from '../../utils/persistence';
import { API_BASE_URL } from '../../config/api.config';

interface MessageLog {
  role: 'user' | 'model';
  parts: string;
}

interface ChatSessionItem {
  id: string;
  title: string;
  date: string;
  pinned: boolean;
  messages?: MessageLog[]; 
}

const NurseonAI: React.FC = () => {
  const [messages, setMessages] = useState<MessageLog[]>(() => loadPersistedState('nurseonAI.messages', []));
  const [userInput, setUserInput] = useState<string>(() => loadPersistedState('nurseonAI.userInput', ''));
  const [hasQueried, setHasQueried] = useState<boolean>(() => loadPersistedState('nurseonAI.hasQueried', false));
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [askLimit, setAskLimit] = useState<number | null>(() => loadPersistedState('nurseonAI.askLimit', null));
  
  const [historySessions, setHistorySessions] = useState<ChatSessionItem[]>(() => loadPersistedState('nurseonAI.historySessions', []));
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(() => loadPersistedState('nurseonAI.currentSessionId', null));
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState<string>('');
  
  const [lastDeletedSession, setLastDeletedSession] = useState<{ item: ChatSessionItem; fullMessages: MessageLog[] } | null>(null);
  const [showUndoToast, setShowUndoToast] = useState<boolean>(false);

  const navigate = useNavigate();
  const chatBottomRef = useRef<HTMLDivElement>(null);
  const uid = localStorage.getItem('user_uid') || "mock_user_id";

  const fetchLimitOnly = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/limit-check`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid })
      });
      if (!response.ok) return;
      const data = await response.json();
      if (data && data.limit_remaining !== undefined) {
        setAskLimit(data.limit_remaining);
      }
    } catch (err) {
      console.error("Failed loading ask limit metrics:", err);
    }
  };

  const fetchHistoryList = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/history/${uid}`);
      if (!response.ok) return;
      const data = await response.json();
      if (data && data.status === 'success') {
        setHistorySessions(data.sessions || []);
      }
    } catch (err) {
      console.error("Failed loading basic history items:", err);
    }
  };

  useEffect(() => {
    savePersistedState('nurseonAI.messages', messages);
    savePersistedState('nurseonAI.userInput', userInput);
    savePersistedState('nurseonAI.hasQueried', hasQueried);
    savePersistedState('nurseonAI.askLimit', askLimit);
    savePersistedState('nurseonAI.historySessions', historySessions);
    savePersistedState('nurseonAI.currentSessionId', currentSessionId);
  }, [messages, userInput, hasQueried, askLimit, historySessions, currentSessionId]);

  useEffect(() => {
    fetchLimitOnly();
    fetchHistoryList();
  }, [uid]);

  const handleNewChat = () => {
    if (loading) return;
    setMessages([]);
    setCurrentSessionId(null);
    setHasQueried(false);
    setErrorMessage('');
    setUserInput('');
  };

  const handleSelectSession = async (sessionId: string) => {
    if (loading) return;
    setLoading(true);
    setErrorMessage('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/history/${uid}/${sessionId}`);
      if (!response.ok) throw new Error('Could not pull your conversation log right now.');
      const data = await response.json();
      
      setMessages(data.messages || []);
      setCurrentSessionId(sessionId);
      setHasQueried(true);
      
      // Refresh the limit when selecting a past session
      await fetchLimitOnly();
    } catch (error: any) {
      parseFriendlyError(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (loading) return;
    setErrorMessage('');
    
    try {
      const fetchResponse = await fetch(`${API_BASE_URL}/api/nurseon-ai/history/${uid}/${sessionId}`);
      if (!fetchResponse.ok) throw new Error("Could not process item removal.");
      const currentThreadData = await fetchResponse.json();

      const itemToDelete = historySessions.find(s => s.id === sessionId);
      if (itemToDelete) {
        setLastDeletedSession({
          item: itemToDelete,
          fullMessages: currentThreadData.messages || []
        });
      }

      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/history/${uid}/${sessionId}`, {
        method: 'DELETE'
      });
      if (!response.ok) throw new Error("Could not remove the item.");

      if (currentSessionId === sessionId) {
        handleNewChat();
      }

      setShowUndoToast(true);
      await fetchHistoryList();
    } catch (err: any) {
      parseFriendlyError(err);
    }
  };

  const handleUndoDelete = async () => {
    if (!lastDeletedSession) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/history/${uid}/${lastDeletedSession.item.id}/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
        item: {
        title: lastDeletedSession.item.title,
        pinned: lastDeletedSession.item.pinned,
        messages: lastDeletedSession.fullMessages,
        date: lastDeletedSession.item.date
        }
      })
      });
      if (!response.ok) throw new Error("Failed to undo deletion.");
      
      setShowUndoToast(false);
      setLastDeletedSession(null);
      await fetchHistoryList();
    } catch (err: any) {
      parseFriendlyError(err);
    }
  };

  const parseFriendlyError = (error: any) => {
    let msg = error.message || String(error);
    
    // Checks if backend returned custom structured JSON object details
    if (msg.includes('{"detail":') || msg.includes('detail')) {
      try {
        const jsonMatch = msg.match(/\{.*\}/);
        if (jsonMatch) {
          const clean = JSON.parse(jsonMatch[0]);
          msg = clean.detail || msg;
        }
      } catch {
        msg = "The system is temporarily busy or your request limit was hit. Please try again in a moment.";
      }
    }
    setErrorMessage(msg);
  };

  const handleRenameSession = async (sessionId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const session = historySessions.find(s => s.id === sessionId);
    if (session) {
      setEditingSessionId(sessionId);
      setEditTitle(session.title);
    }
  };

  const saveRenameSession = async (sessionId: string, e: React.FormEvent) => {
    e.preventDefault();
    if (!editTitle.trim()) return;
    try {
      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/history/${uid}/${sessionId}/rename`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: editTitle.trim() })
      });
      if (response.ok) {
        setEditingSessionId(null);
        await fetchHistoryList();
      }
    } catch (err) {
      console.error("Failed renaming conversation:", err);
    }
  };

  const handleTogglePinSession = async (sessionId: string, currentPinStatus: boolean, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/history/${uid}/${sessionId}/pin`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pinned: !currentPinStatus })
      });
      if (response.ok) {
        await fetchHistoryList();
      }
    } catch (err) {
      console.error("Failed setting conversation pin:", err);
    }
  };

  useEffect(() => {
    if (chatBottomRef.current) {
      chatBottomRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, loading]);

  const handleSearchSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanQuery = userInput.trim();
    if (!cleanQuery || loading || (askLimit !== null && askLimit <= 0)) return;

    if (!localStorage.getItem('user_uid')) {
      setErrorMessage('User session not found. Please log in again.');
      return;
    }

    const currentHistoryState = [...messages];
    const updatedHistoryState: MessageLog[] = [...currentHistoryState, { role: 'user', parts: cleanQuery }];
    
    setMessages(updatedHistoryState);
    setUserInput('');
    setHasQueried(true);
    setLoading(true);
    setErrorMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/nurseon-ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          uid, 
          message: cleanQuery,
          session_id: currentSessionId,
          history: currentHistoryState 
        }),
      });

      if (!response.ok) {
        const fallbackErrorText = await response.text();
        throw new Error(fallbackErrorText || `Communication failure: Status ${response.status}`);
      }

      const data = await response.json();
      setMessages([...updatedHistoryState, { role: 'model', parts: data.reply }]);
      if (data.session_id) setCurrentSessionId(data.session_id);
      if (data.limit_remaining !== undefined) setAskLimit(data.limit_remaining);
      await fetchHistoryList();
    } catch (error: any) {
      parseFriendlyError(error);
    } finally {
      setLoading(false);
    }
  };

  const sortedSessions = [...historySessions].sort((a, b) => {
    if (a.pinned && !b.pinned) return -1;
    if (!a.pinned && b.pinned) return 1;
    return 0;
  });

  return (
    <div className="nurseon-global-container">
      {showUndoToast && (
        <div className="undo-action-banner-toast">
          <span>Delete this chat? This action cannot be undone. Click 'x' to confirm.</span>
          <button className="undo-trigger-action" onClick={handleUndoDelete}>Undo Action</button>
          <button className="undo-close-toast" onClick={() => setShowUndoToast(false)}>✕</button>
        </div>
      )}

      <header className="nurseon-global-top-bar">
        <div className="top-bar-left">
          <button className="back-btn" onClick={() => navigate('/dashboard')} disabled={loading}>
            &larr; Back to Dashboard
          </button>
          <div className="case-title-text-group">
            <h1 className="case-section-heading">Nurse Tutor</h1>
            <p className="case-section-subheading">Need clarifications or inquiry? Ask Nurse Tutor!</p>
          </div>
        </div>
        <div className="top-bar-right" style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          <button className="new-chat-action-btn" onClick={handleNewChat} disabled={loading}>
            + New Chat
          </button>
          <div className="nurseon-ai-limit-pill">
            {askLimit !== null ? (
              `Ask Limits: ${askLimit}/10`
            ) : (
              <span className="limit-loading-skeleton">Updating limit...</span>
            )}
          </div>
        </div>
      </header>

      <div className="nurseon-app-layout-standalone">
        <div className="nurseon-history-text-column">
          <h3 className="history-text-title">Recents</h3>
          {sortedSessions.length === 0 ? (
            <p className="history-text-empty">No recent chats yet.</p>
          ) : (
            <div className="history-text-links-stack">
              {sortedSessions.map((session) => (
                <div
                  key={session.id}
                  onClick={() => handleSelectSession(session.id)}
                  className={`history-text-link-item ${currentSessionId === session.id ? 'active-link' : ''} ${loading ? 'disabled-item' : ''}`}
                >
                  {editingSessionId === session.id ? (
                    <form onSubmit={(e) => saveRenameSession(session.id, e)} className="rename-form-inline" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="rename-input-inline"
                        autoFocus
                        onBlur={(e) => saveRenameSession(session.id, e)}
                      />
                    </form>
                  ) : (
                    <div className="link-item-main-row">
                      <span className="link-item-title">
                        {session.pinned && <span className="pin-marker-indicator">📌 </span>}
                        {session.title}
                      </span>
                      <div className="history-action-trigger-buttons">
                        <button className="action-inline-btn" disabled={loading} onClick={(e) => handleTogglePinSession(session.id, session.pinned, e)}>
                          {session.pinned ? 'Unpin' : 'Pin'}
                        </button>
                        <button className="action-inline-btn" disabled={loading} onClick={(e) => handleRenameSession(session.id, e)}>
                          Rename
                        </button>
                        <button className="action-inline-btn delete-btn" disabled={loading} onClick={(e) => handleDeleteSession(session.id, e)}>
                          Delete
                        </button>
                      </div>
                    </div>
                  )}
                  <span className="link-item-date">{session.date}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="nurseon-ai-wrapper">
          <main className="nurseon-ai-content-core">
            {!hasQueried ? (
              <div className="nurseon-ai-hero-center">
                <h1 className="nurseon-ai-main-title">Hi, I'm your Nurseon AI. How can I help you today?</h1>
                <form onSubmit={handleSearchSubmit} className="nurseon-ai-chat-form">
                  <div className="nurseon-ai-input-wrapper">
                    <input
                      type="text"
                      placeholder="Ask anything"
                      value={userInput}
                      disabled={loading}
                      onChange={(e) => setUserInput(e.target.value)}
                      className="nurseon-ai-chat-input"
                    />
                    <button type="submit" disabled={!userInput.trim() || loading} className="nurseon-ai-send-btn">
                      &rarr;
                    </button>
                  </div>
                </form>
                {errorMessage && <div className="nurseon-ai-error-block">{errorMessage}</div>}
              </div>
            ) : (
              <div className="nurseon-ai-document-view">
                <div className="nurseon-ai-markdown-paper">
                  {messages.map((msg, index) => (
                    <div key={index} className={msg.role === 'user' ? 'nurseon-ai-question' : 'nurseon-ai-answer'}>
                      {msg.role === 'user' ? (
                        <><strong>You:</strong> {msg.parts}</>
                      ) : (
                        <div className="nurseon-ai-markdown-render">
                          <ReactMarkdown>{msg.parts}</ReactMarkdown>
                        </div>
                      )}
                    </div>
                  ))}

                  {loading && (
                    <div className="nurseon-ai-answer" style={{ opacity: 0.7 }}>
                      <p className="nurseon-ai-text-para"><i>Thinking...</i></p>
                    </div>
                  )}
                  <div ref={chatBottomRef} />
                </div>

                <div className="nurseon-ai-active-footer-form">
                  <form onSubmit={handleSearchSubmit} className="nurseon-ai-chat-form">
                    <div className="nurseon-ai-input-wrapper">
                      <input
                        type="text"
                        placeholder={loading ? "Nurseon AI is processing..." : "Ask a follow-up question..."}
                        value={userInput}
                        disabled={loading}
                        onChange={(e) => setUserInput(e.target.value)}
                        className="nurseon-ai-chat-input"
                      />
                      <button type="submit" disabled={!userInput.trim() || loading} className="nurseon-ai-send-btn">
                        {loading ? '...' : '→'}
                      </button>
                    </div>
                  </form>
                  {errorMessage && <div className="nurseon-ai-error-block">{errorMessage}</div>}
                </div>
              </div>
            )}
          </main>

          <div className="case-disclaimer-banner">
            <div className="case-disclaimer-icon">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
              </svg>
            </div>
            <p className="case-disclaimer-text">
              <strong className="disclaimer-highlight">Educational Purposes Only:</strong> This simulation is built to enhance knowledge and boost critical thinking in clinical field and it may carry inappropriate information. For absolute professional practice, please also include and verify with real-world professional nursing guidelines and data-driven textbook knowledge.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default NurseonAI;