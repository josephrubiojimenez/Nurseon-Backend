import React, { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import '../../Styles/PagesStyle/SmartNotes.css';
import { loadPersistedState, savePersistedState } from '../../utils/persistence';
import { API_BASE_URL } from '../../config/api.config';

const SmartNotes: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [instruction, setInstruction] = useState<string>(() => loadPersistedState('smartNotes.instruction', ''));
  const [notes, setNotes] = useState<string>(() => loadPersistedState('smartNotes.notes', ''));
  const [loading, setLoading] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [slotsRemaining, setSlotsRemaining] = useState<number | null>(() => loadPersistedState('smartNotes.slotsRemaining', null));
  const [isCachedNote, setIsCachedNote] = useState<boolean>(false);

  const navigate = useNavigate();

  useEffect(() => {
    savePersistedState('smartNotes.instruction', instruction);
    savePersistedState('smartNotes.notes', notes);
    savePersistedState('smartNotes.slotsRemaining', slotsRemaining);
  }, [instruction, notes, slotsRemaining]);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const uploadedFile = event.target.files?.[0] ?? null;
    setFile(uploadedFile);
    setErrorMessage('');
  };

const handleResetSession = () => {
  if (notes) {
    if (!window.confirm('Are you sure you want to reset? This will clear your generated notes.')) {
      return;
    }
  }
  setInstruction('');
  setNotes('');
  setErrorMessage('');
  setFile(null);
  setIsCachedNote(false);
};

  const generateNotes = async () => {
    if (!file) return;

    const uid = localStorage.getItem('user_uid');
    if (!uid) {
      setErrorMessage('User session not found. Please log in again.');
      return;
    }

    setLoading(true);
    setErrorMessage('');
    setNotes('');
    setIsCachedNote(false);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('instruction', instruction);
    formData.append('uid', uid);

    try {
      const response = await fetch(`${API_BASE_URL}/api/smart-notes/summarize`, {
        method: 'POST',
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to process the file.');
      }

      setNotes(data.summary || '');
      setIsCachedNote(!!data.is_cached);
      
      if (data.slots_remaining !== undefined) {
        setSlotsRemaining(data.slots_remaining);
      }
    } catch (error: any) {
      console.error('Processing error:', error);
      setErrorMessage(error?.message || 'An unexpected server communication fault occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="smart-notes-wrapper">
      <header className="smart-notes-action-header">
        <button className="back-btn" onClick={() => navigate('/dashboard')}>
          &larr; Back to Dashboard
        </button>
      </header>

      <div className="smart-notes-header-meta">
        <div>
          <h1 className="smart-notes-section-heading">Smart Notes</h1>
          <p className="smart-notes-section-subheading">
            Upload Nursing-related documents or images.
          </p>
        </div>

        <div className="smart-notes-header-actions">
          <div className="smart-notes-slots-info">
            Daily Limits: <strong>{slotsRemaining !== null ? slotsRemaining : 5} / 5 Left</strong>
          </div>
          <button 
            type="button" 
            className="smart-notes-reset-btn" 
            onClick={handleResetSession}
            disabled={loading}
            title="Reset"
          >
            Reset
          </button>
        </div>
      </div>

      <div className="smart-notes-form-card">
        <div className="smart-notes-card-header">
          <h1 className="smart-notes-card-title">Documents and Images Summarizer</h1>
          <span className="smart-notes-badge smart-notes-badge-upload">Upload</span>
        </div>
        
        <div className="smart-notes-form">
          <div className="smart-notes-input-group">
            <label className="smart-notes-input-label">
              Upload or Drag File/Image From Your Folder:
            </label>
            <input 
              type="file" 
              accept=".pdf, .png, .jpg, .jpeg, .jfif"
              onChange={handleFileChange}
              className="smart-notes-form-input smart-notes-file-input"
              disabled={loading}
            />
          </div>

          <div className="smart-notes-input-group">
            <label className="smart-notes-input-label">
              What To Focus? (Optional):
            </label>
            <input 
              type="text" 
              placeholder="e.g., Focus heavily on clinical diagnostics, medical management, or nursing care procedures..."
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              className="smart-notes-form-input smart-notes-text-input"
              disabled={loading}
            />
          </div>

          <div className="smart-notes-submit-row">
            <button 
              onClick={generateNotes} 
              disabled={loading || !file}
              className={`smart-notes-submit-btn ${(loading || !file) ? 'disabled-state' : ''}`}
            >
              {loading ? 'Processing...' : 'Upload & Process'}
            </button>
          </div>
        </div>
      </div>

      {errorMessage && (
        <div className="smart-notes-error-banner" style={{
          color: '#721c24',
          backgroundColor: '#f8d7da',
          border: '1px solid #f5c6cb',
          padding: '14px',
          borderRadius: '6px',
          margin: '20px auto 0 auto', 
          maxWidth: '600px',
          fontSize: '14px',
          fontWeight: '500',
          textAlign: 'center'
        }}>
          {errorMessage}
        </div>
      )}

      {loading && (
        <div className="smart-notes-loading">
          <div className="smart-notes-loading-spinner"></div>
          <span className="smart-notes-loading-text">Generating your smart notes...</span>
        </div>
      )}

      {notes && !loading && (
        <div className="smart-notes-output-card smart-notes-fade-in">
          <div className="smart-notes-card-header">
            <h1 className="smart-notes-card-title">Generated Notes</h1>
            <span className={`smart-notes-badge ${isCachedNote ? 'smart-notes-badge-upload' : 'smart-notes-badge-ai'}`}>
              {isCachedNote ? 'Delivered from Cache' : 'Summary'}
            </span>
          </div>
          
          <div className="smart-notes-markdown-body">
            <ReactMarkdown>{notes}</ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
};

export default SmartNotes;