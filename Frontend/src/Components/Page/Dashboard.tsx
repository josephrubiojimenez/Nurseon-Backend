import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import Sidebar from '../Sidebar';
import NurseonFeatures from '../NurseonFeatures';
import ReadDocuments from './ReadDocuments'; 
import SmartNotes from './SmartNotes';
import Quiz from './Quiz';
import CaseStudy from './CaseStudies';
import NurseonAI from './NurseonAIChat';
import MockBoardExam from './MockBoardExam';

// Progress service & utility imports
import { fetchUserProgress, UserProgress } from '../../../services/progressService';
import { loadPersistedState } from '../../utils/persistence';

// Asset imports
import LightMode from '../../assets/Light-mode-icon.png';
import DarkMode from '../../assets/Dark-mode-icon.png';

// Stylesheet imports
import '../../Styles/theme.css';
import '../../Styles/PagesStyle/NurseonDashboard.css';

interface DashboardProps {
  view?: 'default' | 'documents' | 'smart-notes' | 'quiz' | 'case-studies' | 'nurseon-ai' | 'mock-board-exam' | 'profile' | 'progress' | 'insights';
}

interface MockExamSidebarState {
  status: 'running' | 'break';
  timeRemaining: number;
}

const formatTimer = (totalSeconds: number) => {
  const hrs = Math.floor(totalSeconds / 3600);
  const mins = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

const Dashboard: React.FC<DashboardProps> = ({ view = 'default' }) => {
  const navigate = useNavigate();

  // STATE: Metrics matching the comprehensive UserProgress interface from Update
  const [metrics, setMetrics] = useState<UserProgress>({
    quizzesAnswered: 0,
    totalQuizzes: 50,
    caseStudiesCompleted: 0,
    totalCaseStudies: 20,
    mockExamsTaken: 0,
    totalMockExams: 5,
    overallAccuracy: 0,
    latestBoardScore: 0,
    overallBoardScore: 0,
    studyStreak: 0,
    timeSpentHours: 0,
    weaknesses: [],
    weaknessRecommendation: ''
  });

  const [loadingMetrics, setLoadingMetrics] = useState(true);

  // STATE: Theme management
  const [darkMode, setDarkMode] = useState<boolean>(() => {
    const savedTheme = localStorage.getItem('theme');
    return savedTheme === 'dark';
  });
  
  // STATE: Mock Exam Sidebar Countdown Sync
  const [mockExamSidebarInfo, setMockExamSidebarInfo] = useState<MockExamSidebarState | null>(() => {
    if (typeof window === 'undefined') return null;
    const status = loadPersistedState<'selection' | 'running' | 'break' | 'deferred_lock'>('mockExam.examStatus', 'selection');
    const phaseEndTs = loadPersistedState<number>('mockExam.phaseEndTimestamp', 0);
    if (status === 'running' || status === 'break') {
      const timeRemaining = Math.max(0, Math.ceil((phaseEndTs - Date.now()) / 1000));
      return { status, timeRemaining };
    }
    return null;
  });

  // EFFECT: Fetch Initial Metrics from Service
  useEffect(() => {
    const uid = localStorage.getItem('user_uid');
    if (!uid) {
      setLoadingMetrics(false);
      return;
    }

    fetchUserProgress(uid).then(data => {
      setMetrics(data);
      setLoadingMetrics(false);
    });
  }, []);

  // EFFECT: Live listener for feature custom events to invalidate cache and refresh live stats
  useEffect(() => {
    const handleFeatureComplete = () => {
      const uid = localStorage.getItem('user_uid');
      if (uid) {
        // Force refresh (bypass cache)
        fetchUserProgress(uid, true).then(data => {
          setMetrics(data);
        });
      }
    };

    window.addEventListener('quiz-generated', handleFeatureComplete);
    window.addEventListener('case-completed', handleFeatureComplete);
    window.addEventListener('exam-submitted', handleFeatureComplete);

    return () => {
      window.removeEventListener('quiz-generated', handleFeatureComplete);
      window.removeEventListener('case-completed', handleFeatureComplete);
      window.removeEventListener('exam-submitted', handleFeatureComplete);
    };
  }, []);

  // EFFECT: Theme switching synchronization
  useEffect(() => {
    if (darkMode) {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  // EFFECT: Mock exam active tracker countdown interval
  useEffect(() => {
    const syncMockExamCountdown = () => {
      const status = loadPersistedState<'selection' | 'running' | 'break' | 'deferred_lock'>('mockExam.examStatus', 'selection');
      const phaseEndTs = loadPersistedState<number>('mockExam.phaseEndTimestamp', 0);

      if (status === 'running' || status === 'break') {
        const timeRemaining = Math.max(0, Math.ceil((phaseEndTs - Date.now()) / 1000));
        setMockExamSidebarInfo({ status, timeRemaining });
      } else {
        setMockExamSidebarInfo(null);
      }
    };

    syncMockExamCountdown();
    const intervalId = window.setInterval(syncMockExamCountdown, 1000);
    return () => window.clearInterval(intervalId);
  }, []);

  const toggleTheme = () => setDarkMode(!darkMode);

  return (
    <div className="dashboard-container">
      {/* Sidebar gets the background countdown state intact from Current code */}
      <Sidebar mockExamSidebarInfo={mockExamSidebarInfo} />
      
      <div className="main-content-area">
        <header className="top-navbar">
          <button onClick={toggleTheme} className="theme-toggle-btn" aria-label="Toggle theme">
            <img
              src={darkMode ? LightMode : DarkMode}
              className="toggle-icon"
              alt="Theme Toggle"
            />
          </button>
        </header>
        
        <div className="background-container">
          {view === 'documents' ? (
            <ReadDocuments />
          ) : view === 'smart-notes' ? (
            <SmartNotes />
          ) : view === 'quiz' ? (
            <Quiz />
          ) : view === 'case-studies' ? (
            <CaseStudy />
          ) : view === 'nurseon-ai' ? (
            <NurseonAI />
          ) : view === 'mock-board-exam' ? (
            <MockBoardExam />
          ) : view === 'progress' ? (
            <div className="empty-state-card">
              <h2>Progress</h2>
              <p>Your learning progress will appear here.</p>
            </div>
          ) : view === 'insights' ? (
            <div className="empty-state-card">
              <h2>Insights</h2>
              <p>Personalized insights will appear here.</p>
            </div>
          ) : (
            /* Default View: renders the feature board with live fetched metrics and standard loading indicators */
            <NurseonFeatures 
              metrics={metrics} 
              loading={loadingMetrics} 
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default Dashboard;