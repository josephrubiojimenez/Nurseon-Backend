import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';

import LandingPage from './Components/Page/LandingPage';
import NurseonDashboard from './Components/Page/Dashboard';


import './Styles/theme.css';

const rootElement = document.getElementById('nurseon-root'); 
if (!rootElement) throw new Error('Match the root');

createRoot(rootElement).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        
        <Route path="/dashboard" element={<NurseonDashboard view="default" />} />
        <Route path="/progress" element={<NurseonDashboard view="progress" />} />
        <Route path="/insights" element={<NurseonDashboard view="insights" />} />
        <Route path="/read-documents" element={<NurseonDashboard view="documents" />} />
        <Route path="/smart-notes" element={<NurseonDashboard view="smart-notes" />} />
        <Route path="/quiz" element={<NurseonDashboard view="quiz" />} />
        <Route path="/case-studies" element={<NurseonDashboard view="case-studies" />} />
        <Route path="/nurseon-ai" element={<NurseonDashboard view="nurseon-ai" />} />
        <Route path="/mock-board-exam" element={<NurseonDashboard view="mock-board-exam" />} />
        

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>
);