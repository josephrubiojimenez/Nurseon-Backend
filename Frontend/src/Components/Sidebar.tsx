import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import NurseonLogo from '../assets/Nurseon-logo.png';
import Home from '../assets/Home.png';
import Stats from '../assets/Stats.png';
import Profile from '../assets/Profile.png';
import Insights from '../assets/Insights.png';
import '../Styles/Sidebar.css';

interface SidebarProps {
    mockExamSidebarInfo?: { status: 'running' | 'break'; timeRemaining: number } | null;
}

const formatTimer = (totalSeconds: number) => {
    const hrs = Math.floor(totalSeconds / 3600);
    const mins = Math.floor((totalSeconds % 3600) / 60);
    const secs = totalSeconds % 60;
    return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
};

const navItems = [
    { label: 'Dashboard', path: '/dashboard', icon: Home },
    { label: 'Progress', path: '/progress', icon: Stats },
    { label: 'Insights', path: '/insights', icon: Insights },
];

const Sidebar: React.FC<SidebarProps> = ({ mockExamSidebarInfo }) => {
    const location = useLocation();
    const navigate = useNavigate();

    return (
        <div className="sidebar">
            <div className="brand-container">
                <img src={NurseonLogo} className="brand-logo" alt="Nurseon Logo" />
                <h1 className="brand-title">Nurseon</h1>
            </div>
            
            <div className="sidebar-nav-scroll-wrapper">
                <div className="nav-section">
                    <span className="nav-section-title">Navigate</span>
                    <ul className="nav-list">
                        {navItems.map(({ label, path, icon }) => {
                            const isActive = location.pathname === path;

                            return (
                                <li key={label}>
                                    <button
                                        type="button"
                                        className={`nav-icon-box${isActive ? ' active' : ''}`}
                                        onClick={() => navigate(path)}
                                    >
                                        <img src={icon} className="nav-icon" alt={label} />
                                        <span className="nav-label">{label}</span>
                                    </button>
                                </li>
                            );
                        })}
                    </ul>
                </div>
            </div>
            {mockExamSidebarInfo && (
                <div className="sidebar-alarm-card">
                    <div className="sidebar-alarm-dot" />
                    <div className="sidebar-alarm-copy">
                        <span className="sidebar-alarm-title">
                            {mockExamSidebarInfo.status === 'break' ? 'Board Exam Break' : 'Board Exam Active'}
                        </span>
                        <span className="sidebar-alarm-time">{formatTimer(mockExamSidebarInfo.timeRemaining)}</span>
                    </div>
                </div>
            )}
            <div className="profile-container">
                <div className="nav-icon-box profile-box">
                    <div className="profile-group">
                        <img src={Profile} className="profile-avatar" alt="Profile" />
                        <div className="profile-details">
                            <span className="profile-name">Account</span>
                            <span className="profile-subtitle">View Profile</span>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default Sidebar;