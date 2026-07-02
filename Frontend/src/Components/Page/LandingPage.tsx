import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { signInWithEmailAndPassword, createUserWithEmailAndPassword, updateProfile, signInWithPopup } from 'firebase/auth';
import { auth, googleProvider } from '../../firebase.config'; 

import '../../Styles/PagesStyle/LandingPage.css';
import Footer from '../../Components/Footer';
import NurseonLogo from '../../assets/Nurseon-logo.png';
import { API_BASE_URL } from '../../config/api.config';

interface EyeIconProps { open: boolean; }
const EyeIcon = ({ open }: EyeIconProps) => {
    return open ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
    ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
    );
};

const getFriendlyErrorMessage = (error: any): string => {
    const errorCode = error?.code || '';
    const errorMsg = error?.message || '';

    switch (errorCode) {
        case 'auth/invalid-credential':
        case 'auth/wrong-password':
        case 'auth/user-not-found':
            return 'Invalid email or password. Please verify your credentials and try again.';
        case 'auth/invalid-email':
            return 'The email address you entered is incorrectly formatted.';
        case 'auth/user-disabled':
            return 'This user account has been deactivated. Please contact support.';
        case 'auth/email-already-in-use':
            return 'This email address is already registered to an account.';
        case 'auth/weak-password':
            return 'Password is too weak. Please use at least 6 characters.';
        case 'auth/too-many-requests':
            return 'Access has been temporarily blocked due to multiple failed login attempts. Please try again later.';
        case 'auth/network-request-failed':
            return 'Network error. Please check your internet connection and try again.';
        default:
            if (errorMsg.includes('invalid-credential')) {
                return 'Invalid email or password. Please try again.';
            }
            return errorMsg || 'An unexpected authentication error occurred. Please try again.';
    }
};

const LandingPageHeader: React.FC<{ setFormType: (type: 'login' | 'register') => void }> = ({ setFormType }) => {
    return (
        <nav className="header-nav-bar">
            <div className="header-logo" onClick={() => setFormType('login')} style={{ cursor: 'pointer' }}>Nurseon</div>
            <ul className="nav-links">
                <li><a href="#about-section" className="nav-link">About</a></li>
                <li><a href="#contact-section" className="nav-link">Contact</a></li>
            </ul>
        </nav>
    );
};

export default function LandingPage() {
    const navigate = useNavigate();

    const [formType, setFormType] = useState<'login' | 'register'>('login');
    const [showPassword, setShowPassword] = useState<boolean>(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
    const [fullName, setFullName] = useState<string>('');
    const [email, setEmail] = useState<string>('');
    const [password, setPassword] = useState<string>('');
    const [confirmPassword, setConfirmPassword] = useState<string>('');
    
    const [statusMessage, setStatusMessage] = useState<string>('');
    const [statusType, setStatusType] = useState<'error' | 'success'>('error');
    const [loading, setLoading] = useState<boolean>(false);

    const handleFormSwitch = (type: 'login' | 'register') => {
        setFormType(type);
        setStatusMessage('');
        setPassword('');
        setConfirmPassword('');
    };

    const sendTokenToBackend = async (idToken: string, endpoint: 'login' | 'register', nameToRegister?: string) => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/auth/${endpoint}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ token: idToken, name: nameToRegister || null }),
            });
            const backendData = await response.json();
            if (response.ok && backendData.success) {
                if (endpoint === 'register') {
                    setStatusType('success');
                    setStatusMessage('Registration successful! Please sign in using your registered credentials.');
                    setFullName('');
                    setFormType('login');
                    setPassword('');
                    setConfirmPassword('');
                } else {
                    localStorage.setItem('user_uid', backendData.uid);
                    navigate('/dashboard');
                }
            } else {
                throw new Error(backendData.detail || "Error.");
            }
        } catch (err: any) {
            setStatusType('error');
            setStatusMessage(err.message || "Error.");
        } finally {
            setLoading(false);
        }
    };

    const handleEmailLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatusMessage('');
        setLoading(true);
        try {
            const userCredential = await signInWithEmailAndPassword(auth, email, password);
            const idToken = await userCredential.user.getIdToken();
            await sendTokenToBackend(idToken, 'login');
        } catch (err: any) {
            setStatusType('error');
            setStatusMessage(getFriendlyErrorMessage(err));
            setLoading(false);
        }
    };

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setStatusMessage('');

        if (password !== confirmPassword) {
            setStatusType('error');
            setStatusMessage("Password do not match.");
            return;
        }

        setLoading(true);
        try {
            const userCredential = await createUserWithEmailAndPassword(auth, email, password);
            await updateProfile(userCredential.user, { displayName: fullName });
            const idToken = await userCredential.user.getIdToken();
            await sendTokenToBackend(idToken, 'register', fullName);
        } catch (err: any) {
            setStatusType('error');
            setStatusMessage(getFriendlyErrorMessage(err));
            setLoading(false);
        }
    };

    const handleGoogleAuth = async (mode: 'login' | 'register') => {
        setStatusMessage('');
        setLoading(true);
        try {
            const result = await signInWithPopup(auth, googleProvider);
            const idToken = await result.user.getIdToken();
            await sendTokenToBackend(idToken, mode, result.user.displayName || '');
        } catch (err: any) {
            setStatusType('error');
            setStatusMessage(getFriendlyErrorMessage(err));
            setLoading(false);
        }
    };

    return (
        <div className="landing-page-container">
            <LandingPageHeader setFormType={handleFormSwitch} />
            <main className="landing-main-content">
                <div className="text-side">
                    <img src={NurseonLogo} alt="Nurseon" className="landing-brand-logo-large" />
                    <p className="landing-hero-desc">
                        <strong>A comprehensive review and progress-tracking platform</strong> built to help aspiring nurses study smarter, strengthen their knowledge, and confidently achieve exam success.
                    </p>
                    <div className="hero-stat-row">
                        <div className="hero-stat"><span className="hero-stat-num">100%</span><span className="hero-stat-label">Pass rate</span></div>
                        <div className="hero-stat"><span className="hero-stat-num">12K+</span><span className="hero-stat-label">Practice items</span></div>
                        <div className="hero-stat"><span className="hero-stat-num">10</span><span className="hero-stat-label">PNLE areas</span></div>
                    </div>
                </div>

                <div className="login-side">
                    {formType === 'login' ? (
                        <form className="login-form" onSubmit={handleEmailLogin}>
                            <h2>Sign in</h2>
                            
                            {statusMessage && (
                                <p style={{ 
                                    color: statusType === 'success' ? '#155724' : '#721c24', 
                                    backgroundColor: statusType === 'success' ? '#d4edda' : '#f8d7da',
                                    border: `1px solid ${statusType === 'success' ? '#c3e6cb' : '#f5c6cb'}`,
                                    padding: '12px',
                                    borderRadius: '6px',
                                    fontSize: '13px', 
                                    margin: '0 0 16px 0',
                                    lineHeight: '1.4',
                                    fontWeight: '500'
                                }}>
                                    {statusMessage}
                                </p>
                            )}

                            <div className="input-group">
                                <label htmlFor="email">Email Address</label>
                                <input type="email" id="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com" required />
                            </div>

                            <div className="input-group">
                                <div className="password-label-row">
                                    <label htmlFor="password">Password</label>
                                    <a href="/forgot-password" className="forgot-password-link" onClick={(e) => e.preventDefault()}>Forgot password?</a>
                                </div>
                                <div className="password-input-wrapper">
                                    <input type={showPassword ? 'text' : 'password'} id="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
                                    <button type="button" className="password-toggle-btn" onClick={() => setShowPassword((p) => !p)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                                        <EyeIcon open={showPassword} />
                                    </button>
                                </div>
                            </div>

                            <button type="submit" className="login-btn" disabled={loading}>
                                {loading ? "Signing in..." : "Sign In"}
                            </button>

                            <div className="form-divider"><span>or</span></div>

                            <button type="button" className="google-btn" onClick={() => handleGoogleAuth('login')} disabled={loading}>
                                <svg className="google-icon" viewBox="0 0 24 24" width="16" height="16">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05" />
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335" />
                                </svg>
                                Continue with Google
                            </button>

                            <p className="register-redirect">
                                New here?{' '}
                                <a href="#signup" onClick={(e) => { e.preventDefault(); handleFormSwitch('register'); }}>Sign up</a>
                            </p>
                        </form>
                    ) : (
                        <form className="login-form" onSubmit={handleRegister}>
                            <h2>Sign up</h2>
                            
                            {statusMessage && (
                                <p style={{ 
                                    color: '#721c24', 
                                    backgroundColor: '#f8d7da',
                                    border: '1px solid #f5c6cb',
                                    padding: '12px',
                                    borderRadius: '6px',
                                    fontSize: '13px', 
                                    margin: '0 0 16px 0',
                                    lineHeight: '1.4'
                                }}>
                                    {statusMessage}
                                </p>
                            )}

                            <div className="input-group">
                                <label htmlFor="fullName">Full Name</label>
                                <input type="text" id="fullName" value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="your full name" required />
                            </div>

                            <div className="input-group">
                                <label htmlFor="email">Email Address</label>
                                <input type="email" id="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@email.com" required />
                            </div>

                            <div className="input-group">
                                <label htmlFor="password">Password</label>
                                <div className="password-input-wrapper">
                                    <input type={showPassword ? 'text' : 'password'} id="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
                                    <button type="button" className="password-toggle-btn" onClick={() => setShowPassword((p) => !p)} aria-label={showPassword ? 'Hide password' : 'Show password'}>
                                        <EyeIcon open={showPassword} />
                                    </button>
                                </div>
                            </div>

                            <div className="input-group">
                                <label htmlFor="confirmPassword">Confirm Password</label>
                                <div className="password-input-wrapper">
                                    <input type={showConfirmPassword ? 'text' : 'password'} id="confirmPassword" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} placeholder="••••••••" required />
                                    <button type="button" className="password-toggle-btn" onClick={() => setShowConfirmPassword((cp) => !cp)} aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}>
                                        <EyeIcon open={showConfirmPassword} />
                                    </button>
                                </div>
                            </div>

                            <button type="submit" className="login-btn" disabled={loading}>
                                {loading ? "Signing up..." : "Sign Up"}
                            </button>

                            <div className="form-divider"><span>or</span></div>

                            <button type="button" className="google-btn" onClick={() => handleGoogleAuth('register')} disabled={loading}>
                                <svg className="google-icon" viewBox="0 0 24 24" width="16" height="16">
                                    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                                    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                                    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05" />
                                    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335" />
                                </svg>
                                Continue with Google
                            </button>

                            <p className="register-redirect">
                                Already have an account?{' '}
                                <a href="#login" onClick={(e) => { e.preventDefault(); handleFormSwitch('login'); }}>Sign in</a>
                            </p>
                        </form>
                    )}
                </div>
            </main>
            <Footer />
        </div>
    );
}