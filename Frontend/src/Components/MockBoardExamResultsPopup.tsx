import React, { useEffect } from 'react';
import '../Styles/MockBoardExamResultsPopup.css';

interface ResultsPopupProps {
    score: number;
    passed: boolean;
    onContinue: () => void;
}

export const MockBoardExamResultsPopup: React.FC<ResultsPopupProps> = ({ 
    score, 
    passed, 
    onContinue 
}) => {
    // Prevent body scroll when popup is open
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => {
            document.body.style.overflow = 'auto';
        };
    }, []);

    // Allow Escape key to close (optional, depends on UX)
    useEffect(() => {
        const handleKeyPress = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                onContinue();
            }
        };

        window.addEventListener('keydown', handleKeyPress);
        return () => window.removeEventListener('keydown', handleKeyPress);
    }, [onContinue]);

    return (
        <div className="exam-results-overlay" onClick={onContinue}>
            <div className="exam-results-card" onClick={(e) => e.stopPropagation()}>
                {passed ? (
                    <>
                        <div className="results-celebration">🎉</div>
                        <h2 className="results-title">Congratulations!</h2>
                        <p className="results-message">
                            You passed your Mock Board Examination.
                        </p>
                    </>
                ) : (
                    <>
                        <div className="results-encouragement">💪</div>
                        <h2 className="results-title">Keep Going!</h2>
                        <p className="results-message">
                            Don't be discouraged. Review your weak subjects and try again 
                            after strengthening those areas.
                        </p>
                    </>
                )}
                
                <div className="results-score-box">
                    <span className="results-score-label">Score</span>
                    <span className="results-score-value">{score}%</span>
                </div>
                
                {passed && (
                    <p className="results-tip">
                        Keep reviewing your weak areas before taking another exam.
                    </p>
                )}
                
                <button 
                    className="results-continue-btn" 
                    onClick={onContinue}
                    autoFocus  // Focus for keyboard navigation
                >
                    Continue
                </button>
            </div>
        </div>
    );
};