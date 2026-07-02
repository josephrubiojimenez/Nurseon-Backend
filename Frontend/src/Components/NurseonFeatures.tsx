import React from 'react';
import { useNavigate } from 'react-router-dom';

import QuizItIcon from '../assets/quiz-it-icon.png';
import ReadDocIcon from '../assets/Read-docs-icon.png';
import SmartNoteIcon from '../assets/smart-note-icon.png';
import NurseTutorIcon from '../assets/nurse-tutor-icon.png';
import MockExamIcon from '../assets/mock-exam-icon.png';
import CaseStudiesIcon from '../assets/case-studies-icon.png';
import InsightsIcon from '../assets/insights-icon.png';
import ProgressIcon from '../assets/progress-icon.png';

import '../Styles/NurseonFeatures.css';

interface FeaturesMetrics {
  quizzesAnswered: number;
  totalQuizzes: number;
  caseStudiesCompleted: number;
  totalCaseStudies: number;
  mockExamsTaken: number;
  totalMockExams: number;
  overallAccuracy: number;
  studyStreak: number;
  timeSpentHours: number;
}

interface NurseonFeaturesProps {
  metrics?: FeaturesMetrics;
  loading?: boolean;
}

const NurseonFeatures: React.FC<NurseonFeaturesProps> = ({ metrics, loading }) => {
    const navigate = useNavigate();

    const data = metrics || {
        quizzesAnswered: 0,
        totalQuizzes: 50,
        caseStudiesCompleted: 0,
        totalCaseStudies: 20,
        mockExamsTaken: 0,
        totalMockExams: 5,
        overallAccuracy: 0,
        studyStreak: 0,
        timeSpentHours: 0
    };

    const quizPercent = Math.min(100, Math.round((data.quizzesAnswered / Math.max(1, data.totalQuizzes)) * 100));
    const casePercent = Math.min(100, Math.round((data.caseStudiesCompleted / Math.max(1, data.totalCaseStudies)) * 100));
    const mockPercent = Math.min(100, Math.round((data.mockExamsTaken / Math.max(1, data.totalMockExams)) * 100));

    if (loading) {
        return (
            <div className="section-wrapper" style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '300px' }}>
                <p className="section-heading">Loading Your Nurseon Dashboard Metrics...</p>
            </div>
        );
    }

    return (
        <div className="section-wrapper">
            <div>
                <h1 className="section-heading">Features</h1>
                <div className="grid-row-container">
                    
                    <div className="feature-card" id="read-docs" onClick={() => navigate('/read-documents')} style={{ cursor: 'pointer' }}>
                        <div className="card-icon-row">
                            <img src={ReadDocIcon} className="card-icon" alt="Read Documents Icon" />
                        </div>
                        <div className="card-content-wrapper">
                            <h1 className="card-title">Read Documents</h1>
                            <p className="card-description">Build nursing foundation</p>
                            <span className="card-stat-counter">30 Documents Available</span>
                        </div>
                    </div>

                    <div className="feature-card" id="smart-notes" onClick={() => navigate('/smart-notes')} style={{ cursor: 'pointer' }}>
                        <div className="card-icon-row">
                            <img src={SmartNoteIcon} className="card-icon" alt="Smart Notes Icon"/>
                        </div>
                        <div className="card-content-wrapper">
                            <h1 className="card-title">Smart Notes</h1>
                            <p className="card-description">Study smarter, not harder</p>
                            <span className="card-stat-counter">200 Summaries</span>
                        </div>
                    </div>

                    <div className="feature-card" onClick={() => navigate('/quiz')} style={{ cursor: 'pointer' }}>
                        <div className="card-icon-row">
                            <img src={QuizItIcon} className="card-icon" alt="Quiz Icon" />
                        </div>
                        <div className="card-content-wrapper">
                            <h1 className="card-title">Quiz</h1>
                            <p className="card-description">Strengthen clinical knowledge</p>
                            <span className="card-stat-counter">{data.totalQuizzes} Questions</span>
                        </div>
                    </div>

                    <div className="feature-card" onClick={() => navigate('/case-studies')} style={{ cursor: 'pointer' }}>
                        <div className="card-icon-row">
                            <img src={CaseStudiesIcon} className="card-icon" alt="Case Studies Icon" />
                        </div>
                        <div className="card-content-wrapper">
                            <h1 className="card-title">Case Studies</h1>
                            <p className="card-description">Test clinical interventions</p>
                            <span className="card-stat-counter">{data.totalCaseStudies} Cases</span>
                        </div>
                    </div>

                    <div className="feature-card" onClick={() => navigate('/nurseon-ai')} style={{ cursor: 'pointer' }}>
                        <div className="card-icon-row">
                            <img src={NurseTutorIcon} className="card-icon" alt="Nurse Tutor Icon" />
                            <span className="feature-badge badge-ai">AI</span>
                        </div>
                        <div className="card-content-wrapper">
                            <h1 className="card-title">Nurse Tutor</h1>
                            <p className="card-description">Daily study companion</p>
                            <span className="card-stat-counter">Ask Anything</span>
                        </div>
                    </div>

                    <div className="feature-card" onClick={() => navigate('/mock-board-exam')} style={{ cursor: 'pointer' }}>
                        <div className="card-icon-row">
                            <img src={MockExamIcon} className="card-icon" alt="Mock Exam Icon" />
                            <span className="feature-badge badge-popular">Popular</span>
                        </div>
                        <div className="card-content-wrapper">
                            <h1 className="card-title">Mock Board Exam</h1>
                            <p className="card-description">PNLE Preparation</p>
                            <span className="card-stat-counter">Target Pass: 75%</span>
                        </div>
                    </div>

                </div>
            </div>

            <div className="analytics-split-row">
                <div className="analytics-column progress-column">
                    <p className="section-heading progress-heading">Progress</p>
                    <div className="progress-card-box">
                        <div className="detailed-progress-card">
                            <div className="progress-header">
                                <img src={ProgressIcon} className="card-icon" alt="Progress Tracker Icon" />
                                <h1 className="card-title">Progress Tracker</h1>
                            </div>
                            
                            <div className="progress-metrics-list">
                                <div className="metric-row">
                                    <div className="metric-info">
                                        <span className="metric-label">Quizzes Answered</span>
                                        <div className="metric-data-group">
                                            <span className="metric-counter">{data.quizzesAnswered} / {data.totalQuizzes} Qs</span>
                                            <span className="metric-percentage">{quizPercent}%</span>
                                        </div>
                                    </div>
                                    <div className="progress-bar-track">
                                        <div className="progress-bar-fill quiz-fill" style={{ width: `${quizPercent}%` }}></div>
                                    </div>
                                </div>
                                
                                <div className="metric-row">
                                    <div className="metric-info">
                                        <span className="metric-label">Case Studies Completed</span>
                                        <div className="metric-data-group">
                                            <span className="metric-counter">{data.caseStudiesCompleted} / {data.totalCaseStudies} Cases</span>
                                            <span className="metric-percentage">{casePercent}%</span>
                                        </div>
                                    </div>
                                    <div className="progress-bar-track">
                                        <div className="progress-bar-fill cases-fill" style={{ width: `${casePercent}%` }}></div>
                                    </div>
                                </div>
                                
                                <div className="metric-row">
                                    <div className="metric-info">
                                        <span className="metric-label">Mock Exams Overview</span>
                                        <div className="metric-data-group">
                                            <span className="metric-counter">{data.mockExamsTaken} / {data.totalMockExams} Taken</span>
                                            <span className="metric-percentage">{mockPercent}%</span>
                                        </div>
                                    </div>
                                    <div className="progress-bar-track">
                                        <div className="progress-bar-fill mock-fill" style={{ width: `${mockPercent}%` }}></div>
                                    </div>
                                </div>
                            </div>

                            <div className="taken-info">
                                <span className="info-tag item-quizzes">Overall Accuracy: {data.overallAccuracy}%</span>
                                <span className="info-tag item-docs">Study Streak: {data.studyStreak} Days</span>
                                <span className="info-tag item-cases">Time Spent: {data.timeSpentHours}h total</span>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="analytics-column weakness-column">
                    <p className="section-heading progress-heading">Insights</p>
                    <div className="feature-weakness-analysis">
                        <div className="progress-header">
                            <img src={InsightsIcon} className="card-icon" alt="Insights Icon" />
                            <h1 className="card-title">Weakness Analysis</h1>
                        </div>
                        <div className="weakness-content">
                            <p className="weakness-summary">
                                Based on your last {data.mockExamsTaken} mock exams, your accuracy drops on safety and infection control prioritization queries.
                            </p>
                            <ul className="weakness-details-list">
                                <li className="weakness-item">
                                    <span className="weakness-subject">Pharmacology & Parenteral Therapies</span>
                                    <span className="weakness-badge critical">High Priority</span>
                                </li>
                                <li className="weakness-item">
                                    <span className="weakness-subject">Fluid & Electrolyte Imbalances</span>
                                    <span className="weakness-badge medium">Medium Priority</span>
                                </li>
                            </ul>
                            <div className="weakness-action-tip">
                                <strong>Recommended Next Step:</strong> Review the custom smart notes generated for <em>Dosage Calculations</em> before your next mock exam run.
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default NurseonFeatures;