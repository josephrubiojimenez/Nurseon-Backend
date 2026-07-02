import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import '../../Styles/PagesStyle/ReadDocuments.css';
import { loadPersistedState, savePersistedState } from '../../utils/persistence';
import { API_BASE_URL } from '../../config/api.config';
export interface DocumentContent {
    type: 'paragraph' | 'heading';
    text: string;
}

export interface DocumentSource {
    id: string;
    text: string;
}

export interface DocumentData {
    id: string; 
    title: string;
    category: string;
    readTime: string; 
    description: string; 
    publishDate: string;
    content: DocumentContent[];
    sources: DocumentSource[];
}

const ReadDocuments: React.FC = () => {
    const navigate = useNavigate();
    const readerRef = useRef<HTMLDivElement>(null);
    
    const [documents, setDocuments] = useState<DocumentData[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    
    const [activeDocument, setActiveDocument] = useState<DocumentData | null>(() => loadPersistedState('readDocuments.activeDocument', null));
    const [recentDocumentId, setRecentDocumentId] = useState<string | null>(() => loadPersistedState('readDocuments.recentDocumentId', null)); 
    const [savedScrollPosition, setSavedScrollPosition] = useState<number>(() => loadPersistedState('readDocuments.savedScrollPosition', 0));

    useEffect(() => {
        savePersistedState('readDocuments.activeDocument', activeDocument);
        savePersistedState('readDocuments.recentDocumentId', recentDocumentId);
        savePersistedState('readDocuments.savedScrollPosition', savedScrollPosition);
    }, [activeDocument, recentDocumentId, savedScrollPosition]);

    useEffect(() => {
        const fetchDocuments = async () => {
            try {
                setLoading(true);
                const response = await fetch(`${API_BASE_URL}/api/documents/`);

                if (!response.ok) throw new Error(`Server error: ${response.status}`);

                const data = await response.json();
                setDocuments(data);
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchDocuments();
    }, []);

    const handleBackToList = () => {
        setSavedScrollPosition(window.scrollY); 
        setActiveDocument(null);
    };

    const handleReadDocument = (doc: DocumentData, isResume: boolean) => {
        if (!isResume) {
            setSavedScrollPosition(0); 
        }
        setActiveDocument(doc);
        setRecentDocumentId(doc.id);
    };

    useEffect(() => {
        if (activeDocument && savedScrollPosition > 0) {
            const timer = setTimeout(() => {
                window.scrollTo({
                    top: savedScrollPosition,
                    behavior: 'smooth' 
                });
            }, 60);
            
            return () => clearTimeout(timer);
        }
    }, [activeDocument, savedScrollPosition]);

    if (loading) {
        return (
            <div className="read-docs-wrapper">
                <p className="section-subheading" style={{ textAlign: 'center', marginTop: '4rem' }}>
                    Loading documents. Please wait patiently.
                </p>
            </div>
        );
    }

    if (error) {
        return (
            <div className="read-docs-wrapper">
                <header className="docs-action-header">
                    <button className="back-btn" onClick={() => navigate('/dashboard')}>
                        &larr; Return to Safety
                    </button>
                </header>
                <p className="section-subheading" style={{ color: '#ff6b6b', textAlign: 'center' }}>
                    Error connecting to database: {error}
                </p>
            </div>
        );
    }

    if (activeDocument) {
        return (
            <div className="read-docs-wrapper fade-in-view" ref={readerRef}>
                <header className="docs-action-header">
                    <button className="back-btn" onClick={handleBackToList}>
                        &larr; Back to List
                    </button>
                    {savedScrollPosition > 0 && (
                        <span className="scroll-bookmark-indicator">
                             Position Bookmarked
                        </span>
                    )}
                </header>

                <article className="document-reader-clean-view">
                    <div className="reader-meta-row">
                        <span className="reader-meta-text">{activeDocument.readTime || "15 mins"}</span>
                        <span className="reader-meta-text">&bull; Published: {activeDocument.publishDate}</span>
                        <span className="doc-category-badge text-badge-inline">{activeDocument.category}</span>
                    </div>

                    <h1 className="reader-document-title">{activeDocument.title}</h1>
                    <div className="reader-divider"></div>

                    <section className="reader-body-content">
                        {activeDocument.content.map((item, index) => (
                            item.type === 'heading' ? (
                                <h3 key={index} className="reader-content-heading">{item.text}</h3>
                            ) : (
                                <p key={index} className="reader-content-paragraph">{item.text}</p>
                            )
                        ))}
                    </section>

                    <footer className="reader-sources-clean-section">
                        <h4 className="sources-clean-heading">References & Sources</h4>
                        <ul className="sources-clean-list">
                            {activeDocument.sources.map((source) => (
                                <li key={source.id} className="source-clean-item">
                                    <span className="source-clean-index">[{source.id}]</span> {source.text}
                                </li>
                            ))}
                        </ul>
                    </footer>
                </article>
            </div>
        );
    }

    const recentDoc = documents.find(d => d.id === recentDocumentId);
    const remainingDocs = documents.filter(d => d.id !== recentDocumentId);

    return (
        <div className="read-docs-wrapper">
            <header className="docs-action-header">
                <button className="back-btn" onClick={() => navigate('/dashboard')}>
                    &larr; Back to Dashboard
                </button>
            </header>

            <h1 className="section-heading">Read Documents</h1>
            <p className="section-subheading">Build your nursing foundations.</p>

            {recentDoc && (
                <div className="recent-section-block fade-in-view">
                    <h3 className="grid-section-divider-title">Continue Reading</h3>
                    <div className="document-card recent-highlight-card">
                        <div className="doc-badge-row">
                            <span className="doc-category-badge">{recentDoc.category}</span>
                            <div className="recent-flex-badge">
                                <span className="recent-pulse-dot"></span>
                                <span className="doc-time-badge">
                                    {savedScrollPosition > 0 ? "Reading in Progress" : "Just Viewed"} &bull; {recentDoc.readTime}
                                </span>
                            </div>
                        </div>
                        <h2 className="doc-card-title">{recentDoc.title}</h2>
                        <p className="doc-card-description">
                            {savedScrollPosition > 0 
                              ? "Click below to return to your last read position instantly." 
                              : recentDoc.description}
                        </p>
                        <div className="doc-action-row">
                            <button 
                                className="read-now-btn primary-action-btn" 
                                onClick={() => handleReadDocument(recentDoc, true)}
                            >
                                {savedScrollPosition > 0 ? "Resume From Where You Left Off" : "Resume Document"}
                            </button>
                        </div>
                    </div>
                </div>
            )}
            
            <div className="all-documents-block">
                {recentDoc && <h3 className="grid-section-divider-title">All Documents</h3>}
                <div className="documents-grid">
                    {remainingDocs.map((doc) => (
                        <div key={doc.id} className="document-card">
                            <div className="doc-badge-row">
                                <span className="doc-category-badge">{doc.category}</span>
                                <span className="doc-time-badge">{doc.readTime}</span>
                            </div>
                            <h2 className="doc-card-title">{doc.title}</h2>
                            <p className="doc-card-description">{doc.description}</p>
                            <div className="doc-action-row">
                                <button 
                                    className="read-now-btn" 
                                    onClick={() => handleReadDocument(doc, false)}
                                >
                                    Read Document
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default ReadDocuments;