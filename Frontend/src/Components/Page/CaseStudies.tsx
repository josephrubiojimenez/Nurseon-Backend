import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import '../../Styles/PagesStyle/CaseStudies.css';
import { loadPersistedState, savePersistedState } from '../../utils/persistence';
import { API_BASE_URL } from '../../config/api.config';

interface PatientCase {
  patient_name: string;
  title: string;
  patient_complaint: string;
  context: string;
}

interface CaseEvaluation {
  score_percentage: number;
  clinical_rating: string;
  professional_critique: string;
  recommended_response: string;
  medical_references: string;
}

const CaseStudies: React.FC = () => {
  const [topic, setTopic] = useState<string>(() => loadPersistedState('caseStudies.topic', ''));
  const [difficulty, setDifficulty] = useState<string>(() => loadPersistedState('caseStudies.difficulty', 'Standard'));
  const [loading, setLoading] = useState<boolean>(false);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');
  
  // Set to default to 5 to precisely match your case study allowance structure
  const [slotsRemaining, setSlotsRemaining] = useState<number | null>(() => loadPersistedState('caseStudies.slotsRemaining', null));
  const [activeCase, setActiveCase] = useState<PatientCase | null>(() => loadPersistedState('caseStudies.activeCase', null));
  const [studentReply, setStudentReply] = useState<string>(() => loadPersistedState('caseStudies.studentReply', ''));
  const [evaluationResult, setEvaluationResult] = useState<CaseEvaluation | null>(() => loadPersistedState('caseStudies.evaluationResult', null));

  const navigate = useNavigate();
  const terminalEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    savePersistedState('caseStudies.topic', topic);
    savePersistedState('caseStudies.difficulty', difficulty);
    savePersistedState('caseStudies.slotsRemaining', slotsRemaining);
    savePersistedState('caseStudies.activeCase', activeCase);
    savePersistedState('caseStudies.studentReply', studentReply);
    savePersistedState('caseStudies.evaluationResult', evaluationResult);
  }, [topic, difficulty, slotsRemaining, activeCase, studentReply, evaluationResult]);

  useEffect(() => {
    if (terminalEndRef.current) {
      terminalEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [activeCase, evaluating, evaluationResult]);

  const handleGenerateCase = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim() || loading) return;

    const uid = localStorage.getItem('user_uid');
    if (!uid) {
      setErrorMessage('User session not found. Please sign in again.');
      return;
    }

    setLoading(true);
    setErrorMessage('');
    setActiveCase(null);
    setStudentReply('');
    setEvaluationResult(null);

    try {
      const response = await fetch(`${API_BASE_URL}/api/case-studies/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid, topic, difficulty }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Failed to generate patient scenario.');
      }

      setActiveCase(data.case);
      
      // Captures the updated limit payload format from your backend transaction helper
      if (data.limit_remaining !== undefined) {
        setSlotsRemaining(data.limit_remaining);
      } else if (data.slots_remaining !== undefined) {
        setSlotsRemaining(data.slots_remaining);
      }
    } catch (error: any) {
      setErrorMessage(error.message || 'An error occurred while connecting to the clinical simulator.');
    } finally {
      setLoading(false);
    }
  };

  const handleSendResponse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentReply.trim() || !activeCase || evaluating) return;

    const uid = localStorage.getItem('user_uid');
    if (!uid) {
      setErrorMessage('User session not found. Please log in again.');
      return;
    }

    setEvaluating(true);
    setErrorMessage('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/case-studies/evaluate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          uid,
          patient_scenario: `${activeCase.context} - Complaint: ${activeCase.patient_complaint}`,
          student_response: studentReply,
        }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || 'Evaluation failed.');
      }

      setEvaluationResult(data.evaluation);

      // Dispatch event so dashboard updates progress
      window.dispatchEvent(new CustomEvent('case-completed', {
        detail: { uid, difficulty }
      }));
    } catch (error: any) {
      setErrorMessage(error.message || 'Failed to transmit intervention response.');
    } finally {
      setEvaluating(false);
    }
  };

  const handleResetSimulator = () => {
    setActiveCase(null);
    setEvaluationResult(null);
    setStudentReply('');
    setTopic('');
    setErrorMessage('');
  };

  return (
    <div className="case-wrapper">
      <header className="case-action-header">
        <button className="back-btn" onClick={() => navigate('/dashboard')}>
          &larr; Back to Dashboard
        </button>
      </header>

      <div className="case-header-meta">
        <div>
          <h1 className="case-section-heading">Case Study</h1>
          <p className="case-section-subheading">Make a case and share your interventions.</p>
        </div>
        <div className="case-header-actions">
          <div className="case-slots-info">
            Daily Limits: <strong>{slotsRemaining !== null ? slotsRemaining : 5} / 5 Left</strong>
          </div>
          <button type="button" className="case-reset-btn" onClick={handleResetSimulator}>
            Reset
          </button>
        </div>
      </div>

      <div className="case-terminal-container">
        <div className="case-terminal-body">
          {errorMessage && (
            <div className="case-terminal-alert error">
              {errorMessage}
            </div>
          )}

          {loading && (
            <div className="smart-notes-loading">
              <div className="smart-notes-loading-spinner"></div>
              <span className="smart-notes-loading-text">Admitting patient and preparing medical records...</span>
            </div>
          )}

          {!activeCase && !loading && (
            <div className="case-terminal-placeholder">
              Put yourself in a real scenario where a patient needs your care and support.
            </div>
          )}

          {activeCase && (
            <div className="case-transcript-timeline">
              <div className="case-scene-banner">
                <h3>📌 {activeCase.title || 'Acute Ward Scenario'}</h3>
                <p><strong>Patient Clinical History:</strong> {activeCase.context}</p>
              </div>

              <div className="dialogue-bubble patient">
                <span className="speaker-label">{activeCase.patient_name || 'Patient'}:</span>
                <p className="dialogue-text">"{activeCase.patient_complaint}"</p>
              </div>

              {evaluationResult && (
                <div className="dialogue-bubble student"> 
                  <span className="speaker-label">Your Intervention Response:</span>
                  <p className="dialogue-text">"{studentReply}"</p>
                </div>
              )}

              {evaluating && (
                <div className="smart-notes-loading mini">
                  <div className="smart-notes-loading-spinner"></div>
                  <span>Please wait while validating your intervention...</span>
                </div>
              )}

              {evaluationResult && !evaluating && (
                <div className="ai-feedback-workspace">
                  <div className="feedback-score-badge">
                    <span>Clinical Safety Score</span>
                    <strong style={{ color: evaluationResult.score_percentage >= 75 ? '#2dd4bf' : '#f87171' }}>
                      {evaluationResult.score_percentage}%
                    </strong>
                  </div>

                  <div className="feedback-item">
                    <h4>Clinical Competency Rating</h4>
                    <p className={`rating-tag ${evaluationResult.score_percentage >= 75 ? 'passed' : 'failed'}`}>
                      {evaluationResult.clinical_rating}
                    </p>
                  </div>

                  <div className="feedback-item">
                    <h4>Clinical Critique Insights</h4>
                    <p>{evaluationResult.professional_critique}</p>
                  </div>

                  <div className="feedback-item">
                    <h4>Recommended Professional Response Protocol</h4>
                    <blockquote className="professional-recommendation">
                      {evaluationResult.recommended_response}
                    </blockquote>
                  </div>

                  <div className="feedback-item references">
                    <h4>Academic Textbook References</h4>
                    <p>{evaluationResult.medical_references}</p>
                  </div>

                  <button onClick={handleResetSimulator} className="case-terminal-reset-btn">
                    Dismiss Patient
                  </button>
                </div>
              )}

              <div ref={terminalEndRef} />
            </div>
          )}
        </div>

        <div className="case-terminal-footer">
          {!activeCase ? (
            <form onSubmit={handleGenerateCase} className="case-input-form-row">
              <select
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                disabled={loading}
                className="case-terminal-select"
                title="Select difficulty"
              >
                <option value="Easy">Easy</option>
                <option value="Standard">Standard</option>
                <option value="Hard">Hard</option>
              </select>
          
              <input
                type="text"
                placeholder="Enter a typical disease (e.g., Cataract, Sepsis, Asthma)..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                disabled={loading}
                className="case-terminal-input"
              />
              
              <button
                type="submit"
                disabled={loading || !topic.trim()}
                className="case-terminal-send-btn"
              >
                {loading ? 'Finding Patient...' : 'Find'}
              </button>
            </form>
          ) : (
            !evaluationResult && (
              <form onSubmit={handleSendResponse} className="case-input-form-row">
                <input
                  type="text"
                  placeholder="Tell your patient..."
                  value={studentReply}
                  onChange={(e) => setStudentReply(e.target.value)}
                  disabled={evaluating}
                  className="case-terminal-input"
                />
                
                <button
                  type="submit"
                  disabled={!studentReply.trim() || evaluating}
                  className="case-terminal-send-btn execution"
                >
                  {evaluating ? 'Evaluating...' : 'Assess'}
                </button>
              </form>
            )
          )}
        </div>
      </div>

      <div className="case-disclaimer-banner">
        <div className="case-disclaimer-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>
        <p className="case-disclaimer-text">
          <strong className="disclaimer-highlight">Knowledge Assessment Only:</strong> This simulation is built to assess your knowledge only. It does not replace your dynamic clinical decision-making or judgment. For absolute professional practice, please also include and verify with real-world professional nursing guidelines and textbook clinical knowledge.
        </p>
      </div>
    </div>
  );
};

export default CaseStudies;