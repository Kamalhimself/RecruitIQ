import React from 'react';

export default function AlertBanner({ error, success, onCloseError, onCloseSuccess }) {
  if (!error && !success) return null;

  return (
    <div className="toast-stack-container" aria-live="polite">
      {success && (
        <div className="toast-card toast-success" role="alert">
          <div className="toast-icon-badge success">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
              <polyline points="22 4 12 14.01 9 11.01" />
            </svg>
          </div>
          
          <div className="toast-body">
            <div className="toast-header">
              <span className="toast-title">Success</span>
              <span className="toast-time">Just now</span>
            </div>
            <p className="toast-message">{success}</p>
          </div>

          <button 
            type="button"
            className="toast-close-btn"
            onClick={onCloseSuccess}
            title="Dismiss notification"
          >
            ✕
          </button>

          <div className="toast-progress-track">
            <div className="toast-progress-bar success" style={{ animationDuration: '5s' }}></div>
          </div>
        </div>
      )}

      {error && (
        <div className="toast-card toast-error" role="alert">
          <div className="toast-icon-badge error">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>

          <div className="toast-body">
            <div className="toast-header">
              <span className="toast-title error">Attention</span>
              <span className="toast-time">Just now</span>
            </div>
            <p className="toast-message">{error}</p>
          </div>

          <button 
            type="button"
            className="toast-close-btn"
            onClick={onCloseError}
            title="Dismiss notification"
          >
            ✕
          </button>

          <div className="toast-progress-track">
            <div className="toast-progress-bar error" style={{ animationDuration: '8s' }}></div>
          </div>
        </div>
      )}
    </div>
  );
}
