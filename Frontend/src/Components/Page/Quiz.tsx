import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import '../../Styles/PagesStyle/Quiz.css';
import { loadPersistedState, savePersistedState } from '../../utils/persistence';
import { API_BASE_URL } from '../../config/api.config';

interface QuestionItem {
  question: string;
  options: string[];
  correct_answer: string;
  rationale: string;
}

interface UsageResponse {
  status: string;
  slots_remaining: number;
  total_used: number;
  max_limit: number;
  is_limit_reached: boolean;
}

const Quiz: React.FC = () => {
  const [topic, setTopic] = useState<string>(() => loadPersistedState('quiz.topic', ''));
  const [numQuestions, setNumQuestions] = useState<number>(() => loadPersistedState('quiz.numQuestions', 5));
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [slotsRemaining, setSlotsRemaining] = useState<number | null>(() => loadPersistedState('quiz.slotsRemaining', null));
  const [quizQuestions, setQuizQuestions] = useState<QuestionItem[]>(() => loadPersistedState('quiz.questions', []));
  const [selectedAnswers, setSelectedAnswers] = useState<{ [key: number]: string }>(() => loadPersistedState('quiz.selectedAnswers', {}));
  const [showResults, setShowResults] = useState<boolean>(() => loadPersistedState('quiz.showResults', false));
  const [isLimitReached, setIsLimitReached] = useState<boolean>(() => loadPersistedState('quiz.isLimitReached', false));

  const navigate = useNavigate();

  // ==========================================
  // PERSISTENCE
  // ==========================================

  useEffect(() => {
    savePersistedState('quiz.topic', topic);
    savePersistedState('quiz.numQuestions', numQuestions);
    savePersistedState('quiz.slotsRemaining', slotsRemaining);
    savePersistedState('quiz.questions', quizQuestions);
    savePersistedState('quiz.selectedAnswers', selectedAnswers);
    savePersistedState('quiz.showResults', showResults);
    savePersistedState('quiz.isLimitReached', isLimitReached);
  }, [topic, numQuestions, slotsRemaining, quizQuestions, selectedAnswers, showResults, isLimitReached]);

  // ==========================================
  // FETCH CURRENT USAGE ON MOUNT
  // ==========================================

  const fetchCurrentUsage = async () => {
    const uid = localStorage.getItem('user_uid');
    if (!uid) return;

    try {
      const response = await fetch(`${API_BASE_URL}/api/quiz/usage/${uid}`);
      if (response.ok) {
        const data: UsageResponse = await response.json();
        setSlotsRemaining(data.slots_remaining);
        setIsLimitReached(data.is_limit_reached);

        if (data.is_limit_reached && quizQuestions.length === 0) {
          setErrorMessage('Quiz generation limit reached. You can try again tomorrow.\nYour daily limit will reset at midnight. Please check back tomorrow.');
        }
      }
    } catch (error) {
      console.error('Failed to fetch usage:', error);
    }
  };

  useEffect(() => {
    fetchCurrentUsage();
  }, []);

  // ==========================================
  // GENERATE QUIZ
  // ==========================================

  const handleGenerateQuiz = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!topic.trim() || loading) return;

    if (quizQuestions.length > 0 && !showResults) {
      const confirmed = window.confirm('You have an ongoing quiz. Starting a new one will discard it. Continue?');
      if (!confirmed) return;
    }

    const uid = localStorage.getItem('user_uid');
    if (!uid) {
      setErrorMessage('User session not found. Please log in again.');
      return;
    }

    setLoading(true);
    setErrorMessage('');
    setQuizQuestions([]);
    setSelectedAnswers({});
    setShowResults(false);

    try {
      const response = await fetch(`${API_BASE_URL}/api/quiz/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          uid, 
          topic, 
          num_questions: numQuestions 
        }),
      });

      const data = await response.json();

      if (data.slots_remaining !== undefined) {
        setSlotsRemaining(data.slots_remaining);
      }

      if (data.is_limit_reached) {
        setIsLimitReached(true);
        setErrorMessage('Quiz generation limit reached. You can try again tomorrow.\nYour daily limit will reset at midnight. Please check back tomorrow.');
        setQuizQuestions([]);
        setLoading(false);
        return;
      }

      setIsLimitReached(false);

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate quiz.');
      }

      if (data.status === 'success') {
        setQuizQuestions(data.questions || []);

        if (errorMessage.includes('limit')) {
          setErrorMessage('');
        }

        // Dispatch event so dashboard updates progress
        window.dispatchEvent(new CustomEvent('quiz-generated', {
          detail: { uid, topic }
        }));
      }
    } catch (error: any) {
      console.error('Quiz initialization failure:', error);
      setErrorMessage(error.message || 'An explicit server communication failure occurred.');
    } finally {
      setLoading(false);
    }
  };

  // ==========================================
  // CALCULATE SCORE
  // ==========================================

  const calculateScore = () => {
    let correctCount = 0;
    quizQuestions.forEach((item, index) => {
      if (selectedAnswers[index] === item.correct_answer) {
        correctCount++;
      }
    });
    const percentage = Math.round((correctCount / quizQuestions.length) * 100);
    return { correctCount, percentage };
  };

  const scoreInfo = showResults ? calculateScore() : null;

  // ==========================================
  // RESET SESSION
  // ==========================================

  const handleResetSession = () => {
    if (loading) return;

    // Only confirm if there's an active quiz in progress (generated but not submitted)
    if (quizQuestions.length > 0 && !showResults) {
      if (!window.confirm('Are you sure you want to reset? Your current quiz will be cleared.')) {
        return;
      }
    }

    setTopic('');
    setNumQuestions(5);
    setQuizQuestions([]);
    setSelectedAnswers({});
    setShowResults(false);
    setErrorMessage('');
    fetchCurrentUsage();
  };

  // ==========================================
  // RENDER
  // ==========================================

  return (
    <div className="quiz-wrapper">
      <header className="quiz-action-header">
        <button className="back-btn" onClick={() => navigate('/dashboard')}>
          &larr; Back to Dashboard
        </button>
      </header>

      <div className="quiz-header-meta">
        <div>
          <h1 className="quiz-section-heading">Quiz</h1>
          <p className="quiz-section-subheading">Generate your quiz instantly.</p>
        </div>
        <div className="quiz-header-actions">
          <div className="quiz-slots-info">
            Daily Limits: <strong>{slotsRemaining !== null ? slotsRemaining : 0} / 5 Left</strong>
          </div>
          <button 
            type="button" 
            className="case-reset-btn" 
            onClick={handleResetSession}
            disabled={loading}
            title={loading ? 'Please wait...' : 'Reset quiz'}
          >
            {loading ? 'Please wait...' : 'Reset'}
          </button>
        </div>
      </div>

      <div className="quiz-terminal-container">
        <div className="quiz-terminal-body">
          {errorMessage && (
            <div className="quiz-terminal-alert error" style={{ whiteSpace: 'pre-line' }}>
              {errorMessage}
            </div>
          )}

          {loading && (
            <div className="smart-notes-loading">
              <div className="smart-notes-loading-spinner"></div>
              <span className="smart-notes-loading-text">Generating your quiz...</span>
            </div>
          )}

          {quizQuestions.length === 0 && !loading && !errorMessage && (
            <div className="quiz-terminal-placeholder">
              Take a deep breath before answering the quiz.
            </div>
          )}

          {quizQuestions.length === 0 && !loading && errorMessage && !isLimitReached && (
            <div className="quiz-terminal-placeholder">
              Something went wrong. Please try again.
            </div>
          )}

          {quizQuestions.length > 0 && !loading && (
            <div className="quiz-container-block">
              {quizQuestions.map((item, qIndex) => (
                <div key={qIndex} className="quiz-item-block" style={{ marginBottom: '32px' }}>
                  <p className="quiz-question-text">
                    {qIndex + 1}. {item.question}
                  </p>

                  <div className="quiz-options-container">
                    {item.options.map((option, oIndex) => {
                      const isSelected = selectedAnswers[qIndex] === option;
                      const isCorrect = option === item.correct_answer;

                      let targetClass = "quiz-option-item";
                      if (isSelected) targetClass += " selected";
                      if (showResults) {
                        targetClass += " graded";
                        if (isCorrect) targetClass += " correct";
                        else if (isSelected && !isCorrect) targetClass += " incorrect";
                      }

                      return (
                        <button 
                          key={oIndex}
                          disabled={showResults}
                          onClick={() => setSelectedAnswers(prev => ({ ...prev, [qIndex]: option }))}
                          className={targetClass}
                        >
                          {option}
                        </button>
                      );
                    })}
                  </div>

                  {showResults && (
                    <div className="quiz-rationale-box">
                      <strong>Clinical Rationale:</strong> {item.rationale}
                    </div>
                  )}
                </div>
              ))}

              {showResults && scoreInfo && (
                <div className="quiz-score-summary-panel">
                  <div className="quiz-score-heading">Quiz Results</div>
                  <div className="quiz-score-row">
                    <div className="quiz-score-stat">
                      <span className="quiz-stat-label">Your score</span>
                      <span className="quiz-stat-value text-teal">{scoreInfo.correctCount} / {quizQuestions.length}</span>
                    </div>
                    <div className="quiz-score-stat">
                      <span className="quiz-stat-label">Your Performance</span>
                      <span className={`quiz-stat-value ${scoreInfo.percentage >= 75 ? 'text-teal' : 'text-red'}`}>
                        {scoreInfo.percentage}%
                      </span>
                    </div>
                  </div>
                  <div className="quiz-score-footer-note">
                    {scoreInfo.percentage >= 75 
                      ? " * Excellent. You've Passed!" 
                      : " * Retake recommended. Focus on clinical rationales."}
                  </div>
                </div>
              )}

              {!showResults && (
                <button 
                  onClick={() => setShowResults(true)}
                  disabled={Object.keys(selectedAnswers).length < quizQuestions.length}
                  className="quiz-terminal-send-btn"
                  style={{ width: '100%', marginTop: '12px' }}
                >
                  Submit
                </button>
              )}
            </div>
          )}
        </div>

        <div className="quiz-terminal-footer">
          <form onSubmit={handleGenerateQuiz} className="quiz-input-form-row">
            <select
              value={numQuestions}
              onChange={(e) => setNumQuestions(Number(e.target.value))}
              disabled={loading || isLimitReached}
              className="quiz-terminal-select"
              title="Select number of questions"
            >
              <option value={3}>3 Items (min)</option>
              <option value={5}>5 Items</option>
              <option value={10}>10 Items</option>
              <option value={15}>15 Items</option>
              <option value={20}>20 Items (max)</option>
            </select>

            <input 
              type="text" 
              placeholder={isLimitReached ? "Limit reached. Come back tomorrow!" : "i.e., Focus on pharmacological interventions for Type 2 Diabetes..."}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              disabled={loading || isLimitReached}
              className="quiz-terminal-input"
            />
            <button 
              type="submit"
              disabled={loading || !topic.trim() || isLimitReached}
              className="quiz-terminal-send-btn"
            >
              {loading ? 'Making...' : isLimitReached ? 'Limit Reached' : 'Make'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default Quiz;