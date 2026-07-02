import React from 'react';
import Call from '../assets/Call.png';
import Email from '../assets/email.png';
import '../Styles/Footer.css';

export default function Footer() {
    return (
        <footer>
            <div className="footer-card-container">
                <div id="about-section" className="footer-top-row">
                    <div className="footer-brand-column">
                        <div className="footer-brand-title-group">
                            <h2 className="footer-brand-name">Nurseon</h2>
                        </div>
                        <p className="footer-tagline">
                            Advanced study metrics, clinical simulations, and AI-driven review resources for board preparation and nursing excellence.
                        </p>
                        
                        <div id="contact-section" className="footer-contact-block">
                            <div className="footer-contact-item">
                                <img src={Email} alt="Email" className="footer-contact-icon" />
                                <a href="gmail.com">jayminezthegreat18@gmail.com</a>
                            </div>
                            <div className="footer-contact-item">
                                <img src={Call} alt="Phone" className="footer-contact-icon" />
                                <a href="tel:+639939387129">+63 9939 387 129</a>
                            </div>
                        </div>
                    </div>

                    <div className="footer-links-grid">
                        <div className="footer-nav-section">
                            <h3 className="footer-section-heading">Core Features</h3>
                            <ul className="footer-link-list">
                                <li><a href="#read-docs">Read Documents</a></li>
                                <li><a href="#smart-notes">Smart Notes Generator</a></li>
                                <li><a href="#quiz">Adaptive Quizzes</a></li>
                                <li><a href="#nurse-tutor">AI Nurse Tutor</a></li>
                                <li><a href="#case-studies">Clinical Case Studies</a></li>
                                <li><a href="#mock-exam">PNLE Mock Exams</a></li>
                            </ul>
                        </div>

                        <div className="footer-nav-section">
                            <h3 className="footer-section-heading">Analytics & Insights</h3>
                            <ul className="footer-link-list">
                                <li><a href="#progress">Progress Tracker</a></li>
                                <li><a href="#weakness">Weakness Analysis</a></li>
                            </ul>
                        </div>

                        <div className="footer-nav-section">
                            <h3 className="footer-section-heading">Performance Tracking</h3>
                            <ul className="footer-link-list">
                                <li><a href="#score">Average Accuracy Metrics</a></li>
                                <li><a href="#materials">Materials Completed Logs</a></li>
                            </ul>
                        </div>

                        <div className="footer-nav-section">
                            <h3 className="footer-section-heading">Support & Feedback</h3>
                            <ul className="footer-link-list">
                                <li><a href="#countdown">PNLE Exam Countdown</a></li>
                                <li><a href="#recent-activity">Recent Activity Audits</a></li>
                                <li><a href="#report-error">Report Content/AI Error</a></li>
                                <li><a href="#suggestion-feedback">Submit Layout Feedback</a></li>
                            </ul>
                        </div>
                    </div>
                </div>

                <div className="footer-notice-box">
                    <h4 className="footer-notice-title">AI Study Assistant Notice & Scope of Use</h4>
                    <p className="footer-notice-text">
                        Nurseon operates strictly as an educational decision-support tool and board-exam preparation resource. It provides simulated clinical insights, synthetic case summaries, and draft educational recommendations, but does not substitute for accredited institutional curricula or certified medical supervision. 
                    </p>
                </div>

                <div className="footer-meta-row">
                    <div className="footer-copyright-group">
                        <span className="footer-copyright">&copy; {new Date().getFullYear()} Nurseon. High-satisfaction review platform.</span>
                        <span className="footer-ai-version">Nurseon — {new Date().getFullYear()}</span>
                    </div>
                    <div className="footer-legal-inline">
                        <a href="#about">About Platform</a>
                        <a href="#ethics">AI Transparency Report</a>
                        <a href="#privacy">Privacy & Core Data Policy</a>
                        <a href="#terms">Terms of Service</a>
                    </div>
                </div>
            </div>
        </footer>
    );
}