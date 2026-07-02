import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import '../../Styles/PagesStyle/MockBoardExam.css';
import { loadPersistedState, savePersistedState } from '../../utils/persistence';
import { API_BASE_URL } from '../../config/api.config';
import { MockBoardExamResultsPopup } from '../MockBoardExamResultsPopup';

const BLOCK_TIME_SECONDS = 5400; // 1:30:00 per segment block

interface OptionMap {
  A: string;
  B: string;
  C: string;
  D: string;
  [key: string]: string;
}

interface QuestionItem {
  id: string;
  question: string;
  options: OptionMap;
}

const MockBoardExam: React.FC = () => {
  const navigate = useNavigate();
  const uid = localStorage.getItem('user_uid') || "mock_user_id";

  // Flow states: 'selection' | 'running' | 'break' | 'deferred_lock'
  const [examStatus, setExamStatus] = useState<'selection' | 'running' | 'break' | 'deferred_lock'>(() => loadPersistedState('mockExam.examStatus', 'selection'));
  const [examId, setExamId] = useState<string>(() => loadPersistedState('mockExam.examId', ''));
  const [allQuestions, setAllQuestions] = useState<QuestionItem[]>(() => loadPersistedState('mockExam.allQuestions', []));
  const [currentIndex, setCurrentIndex] = useState<number>(() => loadPersistedState('mockExam.currentIndex', 0));
  
  // Active segments tracking: 'easy' (1-30) | 'medium' (31-60) | 'hard' (61-100)
  const [activeTier, setActiveTier] = useState<'easy' | 'medium' | 'hard'>(() => loadPersistedState('mockExam.activeTier', 'easy'));

  // Time metrics tracking
  const initialPhaseEndTimestamp = loadPersistedState<number>('mockExam.phaseEndTimestamp', 0);
  const savedSeconds = loadPersistedState<number>('mockExam.secondsRemaining', BLOCK_TIME_SECONDS);
  const savedBreakSeconds = loadPersistedState<number>('mockExam.breakSecondsRemaining', 0);
  const [phaseEndTimestamp, setPhaseEndTimestamp] = useState<number>(initialPhaseEndTimestamp);
  const [secondsRemaining, setSecondsRemaining] = useState<number>(() => {
    if (initialPhaseEndTimestamp > 0) {
      return Math.max(0, Math.ceil((initialPhaseEndTimestamp - Date.now()) / 1000));
    }
    return savedSeconds;
  });
  const [breakSecondsRemaining, setBreakSecondsRemaining] = useState<number>(() => {
    const initialStatus = loadPersistedState<'selection' | 'running' | 'break' | 'deferred_lock'>('mockExam.examStatus', 'selection');
    if (initialStatus === 'break') {
      return initialPhaseEndTimestamp > 0
        ? Math.max(0, Math.ceil((initialPhaseEndTimestamp - Date.now()) / 1000))
        : savedBreakSeconds;
    }
    return 0;
  });
  const [pendingIndexAfterBreak, setPendingIndexAfterBreak] = useState<number>(() => loadPersistedState('mockExam.pendingIndexAfterBreak', 0));
  
  const [selectedAnswers, setSelectedAnswers] = useState<Record<string, string>>(() => loadPersistedState('mockExam.selectedAnswers', {}));
  const [flaggedItems, setFlaggedItems] = useState<Record<string, boolean>>(() => loadPersistedState('mockExam.flaggedItems', {}));
  const [loading, setLoading] = useState<boolean>(false);
  const [scoreReleaseInfo, setScoreReleaseInfo] = useState<string>(() => loadPersistedState('mockExam.scoreReleaseInfo', ''));
  const [slotsRemaining, setSlotsRemaining] = useState<number | null>(() => loadPersistedState('mockExam.slotsRemaining', null));
  const [errorMessage, setErrorMessage] = useState<string>('');

  // Results Popup States
  const [showResultsPopup, setShowResultsPopup] = useState<boolean>(false);
  const [examResult, setExamResult] = useState<{ score: number; passed: boolean } | null>(null);

  useEffect(() => {
    savePersistedState('mockExam.examStatus', examStatus);
    savePersistedState('mockExam.examId', examId);
    savePersistedState('mockExam.allQuestions', allQuestions);
    savePersistedState('mockExam.currentIndex', currentIndex);
    savePersistedState('mockExam.activeTier', activeTier);
    savePersistedState('mockExam.phaseEndTimestamp', phaseEndTimestamp);
    savePersistedState('mockExam.secondsRemaining', secondsRemaining);
    savePersistedState('mockExam.breakSecondsRemaining', breakSecondsRemaining);
    savePersistedState('mockExam.pendingIndexAfterBreak', pendingIndexAfterBreak);
    savePersistedState('mockExam.selectedAnswers', selectedAnswers);
    savePersistedState('mockExam.flaggedItems', flaggedItems);
    savePersistedState('mockExam.scoreReleaseInfo', scoreReleaseInfo);
    savePersistedState('mockExam.slotsRemaining', slotsRemaining);
  }, [examStatus, examId, allQuestions, currentIndex, activeTier, phaseEndTimestamp, secondsRemaining, breakSecondsRemaining, pendingIndexAfterBreak, selectedAnswers, flaggedItems, scoreReleaseInfo, slotsRemaining]);

  // Running Active Segment Countdown
  useEffect(() => {
    if (examStatus !== 'running') return;

    const updateRunningTimer = () => {
      const remainingSeconds = phaseEndTimestamp > 0
        ? Math.max(0, Math.ceil((phaseEndTimestamp - Date.now()) / 1000))
        : 0;

      setSecondsRemaining(remainingSeconds);
      if (remainingSeconds <= 0) {
        handleSegmentTimeout();
      }
    };

    updateRunningTimer();
    const timer = setInterval(updateRunningTimer, 1000);
    return () => clearInterval(timer);
  }, [examStatus, phaseEndTimestamp, activeTier, currentIndex]);

  // Break Countdown Intermission Timer
  useEffect(() => {
    if (examStatus !== 'break') return;

    const updateBreakTimer = () => {
      const remainingSeconds = phaseEndTimestamp > 0
        ? Math.max(0, Math.ceil((phaseEndTimestamp - Date.now()) / 1000))
        : 0;

      setBreakSecondsRemaining(remainingSeconds);
      if (remainingSeconds <= 0) {
        setCurrentIndex(pendingIndexAfterBreak);
        setExamStatus('running');
        setPhaseEndTimestamp(Date.now() + BLOCK_TIME_SECONDS * 1000);
      }
    };

    updateBreakTimer();
    const timer = setInterval(updateBreakTimer, 1000);
    return () => clearInterval(timer);
  }, [examStatus, phaseEndTimestamp, pendingIndexAfterBreak]);

  const formatTimer = (totalSeconds: number) => {
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const startUnifiedExam = async () => {
    setLoading(true);
    setErrorMessage('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/mock-board-exam/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid })
      });
      
      const data = await res.json();
      if (res.ok) {
        setAllQuestions(data.questions);
        setExamId(data.exam_id);
        setCurrentIndex(0);
        setActiveTier('easy');
        setSelectedAnswers({});
        setFlaggedItems({});
        setPhaseEndTimestamp(Date.now() + BLOCK_TIME_SECONDS * 1000);
        setSecondsRemaining(BLOCK_TIME_SECONDS);
        
        if (data.limit_remaining !== undefined) {
          setSlotsRemaining(data.limit_remaining);
        } else if (data.slots_remaining !== undefined) {
          setSlotsRemaining(data.slots_remaining);
        }
        
        setExamStatus('running');
      } else {
        setErrorMessage(data.detail || "Initialization error occurred.");
      }
    } catch (err) {
      console.error(err);
      setErrorMessage("Failed to connect to the examination service.");
    } finally {
      setLoading(false);
    }
  };

  const navigateToQuestion = (index: number) => {
    const targetQNum = index + 1;

    // Easy Tier Controls
    if (activeTier === 'easy') {
      if (targetQNum <= 30) {
        setCurrentIndex(index);
      } else if (targetQNum === 31) {
        setPendingIndexAfterBreak(index);
        triggerBreakInterval(600); // 10 Minutes rest 
        setActiveTier('medium');
      }
    } 
    // Medium Tier Controls
    else if (activeTier === 'medium') {
      if (targetQNum >= 31 && targetQNum <= 60) {
        setCurrentIndex(index);
      } else if (targetQNum === 61) {
        setPendingIndexAfterBreak(index);
        triggerBreakInterval(1200); // 20 Minutes rest
        setActiveTier('hard');
      }
    } 
    // Hard Tier Controls
    else if (activeTier === 'hard') {
      if (targetQNum >= 61 && targetQNum <= 100) {
        setCurrentIndex(index);
      }
    }
  };

  const triggerBreakInterval = (durationSeconds: number) => {
    setBreakSecondsRemaining(durationSeconds);
    setPhaseEndTimestamp(Date.now() + durationSeconds * 1000);
    setExamStatus('break');
  };

  const handleSegmentTimeout = () => {
    if (activeTier === 'easy') {
      navigateToQuestion(30); 
    } else if (activeTier === 'medium') {
      navigateToQuestion(60); 
    } else {
      submitEntireExamForm();  
    }
  };

  const submitEntireExamForm = async () => {
    if (!examId) return;

    setLoading(true);
    setErrorMessage('');
    try {
      const res = await fetch(`${API_BASE_URL}/api/mock-board-exam/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid, exam_id: examId, answers: selectedAnswers })
      });
      const data = await res.json();
      
      if (!res.ok) {
        throw new Error(data.detail || "Submission failed.");
      }

      // Legacy flow tracking configuration updates
      const releaseDateStr = data.release_at ? new Date(data.release_at).toLocaleString() : new Date().toLocaleString();
      setScoreReleaseInfo(releaseDateStr);
      setExamStatus('deferred_lock');

      // Calculate score from server response metrics
      const scorePercent = (data.calculated_score / 100) * 100;
      const passed = scorePercent >= 75;

      // Mount modal tracking presentation metrics
      setExamResult({
        score: Math.round(scorePercent),
        passed
      });
      setShowResultsPopup(true);

      // Dispatch tracking configurations to active listener layouts
      window.dispatchEvent(new CustomEvent('exam-submitted', {
        detail: { uid: localStorage.getItem('user_uid'), score: scorePercent }
      }));

    } catch (err: any) {
      console.error(err);
      setErrorMessage(err.message || "Failed to connect to the examination service.");
    } finally {
      setLoading(false);
    }
  };

  const handleResultsPopupContinue = async () => {
    setShowResultsPopup(false);
    
    // Reset layout structural properties safely
    setExamId('');
    setSelectedAnswers({});
    setAllQuestions([]);
    setErrorMessage('');
    
    // Redirect navigation contexts
    navigate('/dashboard');
  };

  const resetScoreCountdown = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/mock-board-exam/reset-score-release`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid, exam_id: examId })
      });
      const data = await res.json();
      if (res.ok) {
        const releaseDateStr = new Date(data.release_at).toLocaleString();
        setScoreReleaseInfo(releaseDateStr);
        alert('Score countdown has been reset! Results are now available immediately.');
      } else {
        alert(data.detail || "Failed to reset score countdown.");
      }
    } catch (err) {
      console.error(err);
      alert("Failed to connect to the examination service.");
    } finally {
      setLoading(false);
    }
  };

  const resetExamEntirely = async () => {
    if (!window.confirm('This will completely reset your exam data and allow you to start a new exam. Are you sure?')) {
      return;
    }
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/mock-board-exam/reset-exam-entirely`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid })
      });
      if (res.ok) {
        setExamStatus('selection');
        setExamId('');
        setAllQuestions([]);
        setCurrentIndex(0);
        setActiveTier('easy');
        setPhaseEndTimestamp(0);
        setSecondsRemaining(BLOCK_TIME_SECONDS);
        setBreakSecondsRemaining(0);
        setPendingIndexAfterBreak(0);
        setSelectedAnswers({});
        setFlaggedItems({});
        setScoreReleaseInfo('');
        setSlotsRemaining(null);
        setErrorMessage('');
        
        Object.keys(localStorage).forEach(key => {
          if (key.startsWith('mockExam.')) {
            localStorage.removeItem(key);
          }
        });
        
        alert('Exam has been completely reset! You can now start a new exam.');
        navigate('/dashboard');
      } else {
        const data = await res.json();
        alert(data.detail || "Failed to reset exam.");
      }
    } catch (err) {
      console.error(err);
      alert("Failed to connect to the examination service.");
    } finally {
      setLoading(false);
    }
  };

  const getTierHeaderMeta = () => {
    switch (activeTier) {
      case 'easy': return { label: "EASY TIERS (NP I & II)", range: "Questions 1 - 30" };
      case 'medium': return { label: "MEDIUM TIERS (NP III)", range: "Questions 31 - 60" };
      case 'hard': return { label: "HARD TIERS (NP IV & V)", range: "Questions 61 - 100" };
    }
  };

  const isPreviousDisabled = () => {
    if (currentIndex === 0) return true;
    if (activeTier === 'medium' && currentIndex === 30) return true; 
    if (activeTier === 'hard' && currentIndex === 60) return true;   
    return false;
  };

  if (examStatus === 'selection') {
    return (
      <div className="exam-selection-viewport">
        <header className="quiz-action-header">
          <button className="back-btn" onClick={() => navigate('/dashboard')}>
            &larr; Back to Dashboard
          </button>
        </header>
        <h2>Comprehensive Mock Board Exam</h2>
        <p className="subtitle">100 items unified questions across three difficulty levels.</p>
        
        {errorMessage && (
          <div className="exam-terminal-alert error">
            {errorMessage}
          </div>
        )}
        
        <div className="session-cards-wrapper">
          <div className="session-card">
            <h3>Coverage of the Exam</h3>
            <span className="exam-coverage-text">
              • <b>1 - 30 | Easy:</b> (NP I & II) - Community Health Nursing, and Maternal and Child Nursing<br/>
              • <b>31 - 60 | Medium:</b> (NP III) - Medical-Surgical Nursing <i>(after 10 minutes break)</i><br/>
              • <b>61 - 100 | Hard:</b> (NP IV & V) - Medical-Surgical Nursing with Psychiatric Nursing Concepts <i>(after 20 minutes break)</i>
            </span>
            
            <p className="exam-slots-count-meta" style={{ marginTop: '15px', color: '#94a3b8' }}>
              Attempts Remaining Today: <strong>{slotsRemaining !== null ? slotsRemaining : 5} / 5</strong>
            </p>
            
            <p className="exam-simple-notice">
              <strong>Notice:</strong> Once you skip a section, you cannot return to it. Take a deep breath and focus before beginning.
            </p>
            
             <button 
               className="start-exam-action-btn" 
               onClick={startUnifiedExam}
               disabled={loading}
             >
               {loading ? 'Launching...' : 'Launch Comprehensive Board'}
             </button>
          </div>
        </div>
        
        <div className="exam-external-notice">
          <div className="exam-external-notice-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10"></circle>
              <line x1="12" y1="8" x2="12" y2="12"></line>
              <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
          </div>
          <p className="exam-external-notice-text">
            <strong className="external-notice-highlight">Knowledge Assessment Only:</strong> This simulation is built to assess your knowledge only. It does not replace your dynamic clinical decision-making or judgment. For absolute professional practice, please verify choices with real-world professional nursing guidelines and textbook clinical knowledge.
          </p>
        </div>
      </div>
    );
  }

  if (examStatus === 'break') {
    return (
      <div className="exam-status-lockout-center">
        <div className="lockout-card">
          <h2>Mandatory Rest Interval Period</h2>
          <p>Segment completed successfully. Relax your focus before loading the next tier setup.</p>
          <div className="break-timer-digits">{formatTimer(breakSecondsRemaining)}</div>
          <p className="disclaimer-note">The next challenge block automatically unlocks when the countdown ends.</p>
        </div>
      </div>
    );
  }

  if (examStatus === 'deferred_lock') {
    return (
      <div className="exam-status-lockout-center">
        <div className="lockout-card secure-lock">
          <div className="icon-clock">🔒</div>
          <h2>Form Submission Successful</h2>
          <p>Your answers have been securely logged. Your full 100-question response is under background evaluation.</p>
          <div className="score-reveal-pill">Results Release Target: {scoreReleaseInfo}</div>
          <div className="exam-button-group">
            <button 
              className="return-dashboard-btn" 
              onClick={resetScoreCountdown}
              disabled={loading}
            >
              {loading ? "Resetting..." : "⚡ View Scores Now"}
            </button>
            <button 
              className="return-dashboard-btn exam-btn-reset" 
              onClick={resetExamEntirely}
              disabled={loading}
            >
              {loading ? "Resetting..." : "🔄 Reset Exam Completely"}
            </button>
            <button 
              className="return-dashboard-btn exam-btn-back" 
              onClick={() => navigate('/dashboard')}
            >
              Back to Dashboard
            </button>
          </div>
        </div>

        {showResultsPopup && examResult && (
          <MockBoardExamResultsPopup
            score={examResult.score}
            passed={examResult.passed}
            onContinue={handleResultsPopupContinue}
          />
        )}
      </div>
    );
  }

  const currentQuestion = allQuestions[currentIndex];
  const isFlagged = flaggedItems[currentQuestion?.id];
  const tierMeta = getTierHeaderMeta();

  return (
    <div className="board-exam-workspace-container">
      <header className="quiz-action-header">
        <button className="back-btn" onClick={() => navigate('/dashboard')}>
          &larr; Back to Dashboard
        </button>
      </header>
      {slotsRemaining !== null && slotsRemaining <= 1 && (
        <div className="limit-info-banner">
          ⚠️ Daily Limit: Only {slotsRemaining} attempt remaining today.
        </div>
      )}
      <header className="board-exam-meta-header">
        <div className="meta-left">
          <span className="exam-pill-badge">{tierMeta.label}</span>
          <span className="progress-text-track">{tierMeta.range} — Current: Item #{currentIndex + 1}</span>
        </div>
        <div className="meta-right">
          <div className="countdown-timer-box">
            <span className="timer-label">CURRENT SEGMENT METER</span>
            <span className="timer-countdown">{formatTimer(secondsRemaining)}</span>
          </div>
        </div>
      </header>

      <div className="board-exam-workspace-split">
        <div className="board-question-main-frame">
          <div className="question-content-header-row">
            <button 
              className={`flag-toggle-action ${isFlagged ? 'active-flagged' : ''}`}
              onClick={() => setFlaggedItems(prev => ({ ...prev, [currentQuestion.id]: !prev[currentQuestion.id] }))}
            >
              🚩 {isFlagged ? 'Flagged' : 'Flag Question'}
            </button>
          </div>

          <div className="question-text-block">
            <p className="clinical-case-scenario">{currentQuestion?.question}</p>
          </div>

          <div className="board-options-shading-matrix">
            {currentQuestion && currentQuestion.options ? (
              Object.entries(currentQuestion.options).map(([key, val]) => {
                const isSelected = selectedAnswers[currentQuestion.id] === key;
                return (
                  <div 
                    key={key} 
                    className={`shading-option-row ${isSelected ? 'shaded-selected' : ''}`}
                    onClick={() => setSelectedAnswers(prev => ({ ...prev, [currentQuestion.id]: key }))}
                  >
                    <div className="bullet-circle-indicator"><div className="inner-filled-dot"></div></div>
                    <span className="option-letter">{key}.</span>
                    <span className="option-body-text">{val}</span>
                  </div>
                );
              })
            ) : (
              <p className="exam-formatting-text">Formatting clinical choices block...</p>
            )}
          </div>

          <footer className="workspace-pagination-footer">
            <button 
              className="footer-nav-btn"
              onClick={() => navigateToQuestion(currentIndex - 1)}
              disabled={isPreviousDisabled()}
            >
              &larr; Prev
            </button>

            {currentIndex === allQuestions.length - 1 ? (
              <button className="footer-submit-action-btn" onClick={submitEntireExamForm} disabled={loading}>
                {loading ? "Securing Exam..." : "Complete & Submit Form"}
              </button>
            ) : (
              <button 
                className="footer-nav-btn next-action-btn"
                onClick={() => navigateToQuestion(currentIndex + 1)}
              >
                Next / Skip &rarr;
              </button>
            )}
          </footer>
        </div>

        <aside className="board-bullets-navigator-aside">
          <h4 className="navigator-title-custom">
            {activeTier === 'easy' && `NP I & II Matrix (1 - 30)`}
            {activeTier === 'medium' && `NP III Matrix (31 - 60)`}
            {activeTier === 'hard' && `NP IV & V Matrix (61 - 100)`}
          </h4>
          
          <div className="bullets-grid-container">
            {allQuestions
              .map((q, idx) => ({ q, originalIndex: idx }))
              .filter(({ originalIndex }) => {
                const qNum = originalIndex + 1;
                if (activeTier === 'easy') return qNum <= 30;
                if (activeTier === 'medium') return qNum >= 31 && qNum <= 60;
                if (activeTier === 'hard') return qNum >= 61 && qNum <= 100;
                return false;
              })
              .map(({ q, originalIndex }) => {
                const hasAnswer = !!selectedAnswers[q.id];
                const isItemFlagged = !!flaggedItems[q.id];
                const isCurrent = originalIndex === currentIndex;

                let cellClass = '';
                if (isCurrent) cellClass = 'cell-current';
                else if (isItemFlagged) cellClass = 'cell-flagged';
                else if (hasAnswer) cellClass = 'cell-shaded';

                return (
                  <button 
                    key={q.id}
                    className={`matrix-bullet-cell ${cellClass}`}
                    onClick={() => navigateToQuestion(originalIndex)}
                  >
                    <span className="cell-num">{originalIndex + 1}</span>
                    {hasAnswer && <span className="shading-letter-sub">{selectedAnswers[q.id]}</span>}
                  </button>
                );
              })}
          </div>
        </aside>
      </div>
    </div>
  );
};

export default MockBoardExam;