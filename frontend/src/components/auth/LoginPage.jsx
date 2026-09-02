import React, { useState, useEffect } from 'react';
import { API_BASE, setAuthSession } from '../../config/api';

export default function LoginPage({ onLoginSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;

  // Initialize Google Identity Services if client ID is provided
  useEffect(() => {
    if (!googleClientId) return;

    // Load GIS script dynamically
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      if (window.google?.accounts?.id) {
        window.google.accounts.id.initialize({
          client_id: googleClientId,
          callback: handleGoogleResponse,
        });
        const buttonDiv = document.getElementById('google-signin-btn');
        if (buttonDiv) {
          window.google.accounts.id.renderButton(buttonDiv, {
            theme: 'filled_blue',
            size: 'large',
            width: 280,
            text: 'signin_with',
            shape: 'rectangular',
          });
        }
      }
    };
    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, [googleClientId]);

  const handleGoogleResponse = async (response) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: response.credential }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Authentication failed');
      }
      setAuthSession(data.access_token, data.user);
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Google SSO login failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleDevLogin = async (customEmail = 'kamaleswar@velansys.com') => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/auth/dev-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          email: customEmail,
          name: customEmail.includes('velansys') ? 'Kamaleswar Sivashanmugam' : 'Recruiter Admin',
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Login failed');
      }
      setAuthSession(data.access_token, data.user);
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Login failed. Verify backend server is running.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(ellipse at top, #1e1b4b 0%, #090d16 60%, #030712 100%)',
      padding: '24px',
      fontFamily: 'Inter, system-ui, sans-serif',
      color: '#f8fafc',
    }}>
      <div style={{
        maxWidth: '440px',
        width: '100%',
        background: 'rgba(15, 23, 42, 0.75)',
        border: '1px solid rgba(99, 102, 241, 0.25)',
        boxShadow: '0 20px 40px -15px rgba(0, 0, 0, 0.7), 0 0 50px -10px rgba(99, 102, 241, 0.15)',
        backdropFilter: 'blur(16px)',
        borderRadius: '16px',
        padding: '36px 32px',
        textAlign: 'center',
      }}>
        {/* Brand Icon & Title */}
        <div style={{
          display: 'inline-flex',
          padding: '12px',
          borderRadius: '16px',
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.2) 0%, rgba(168, 85, 247, 0.2) 100%)',
          border: '1px solid rgba(168, 85, 247, 0.3)',
          marginBottom: '16px',
        }}>
          <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#a855f7" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="6" />
            <circle cx="12" cy="12" r="2" />
          </svg>
        </div>

        <h1 style={{ fontSize: '24px', fontWeight: '700', letterSpacing: '-0.02em', margin: '0 0 6px 0', color: '#ffffff' }}>
          RecruitIQ
        </h1>
        <p style={{ fontSize: '13px', color: '#94a3b8', margin: '0 0 28px 0' }}>
          Enterprise Candidate Matching & Recruitment Automation
        </p>

        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.35)',
            borderRadius: '8px',
            padding: '10px 14px',
            marginBottom: '20px',
            fontSize: '13px',
            color: '#fca5a5',
            textAlign: 'left',
          }}>
            {error}
          </div>
        )}

        {/* Google SSO Container */}
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px', marginBottom: '24px' }}>
          <div id="google-signin-btn" style={{ minHeight: '44px' }}></div>

          <button
            type="button"
            onClick={() => handleDevLogin('kamaleswar@velansys.com')}
            disabled={loading}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              padding: '11px 16px',
              background: '#ffffff',
              color: '#0f172a',
              border: 'none',
              borderRadius: '8px',
              fontSize: '14px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 2px 8px rgba(0, 0, 0, 0.25)',
              transition: 'all 0.2s ease',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 24 24">
              <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"/>
              <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.26v3.15C3.25 21.37 7.34 24 12 24z"/>
              <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.26C.46 8.17 0 9.97 0 12s.46 3.83 1.26 5.42l4.02-3.15z"/>
              <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.34 0 3.25 2.63 1.26 6.58l4.02 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
            </svg>
            {loading ? 'Authenticating...' : 'Sign in with Google Workspace'}
          </button>
        </div>

        {/* Divider */}
        <div style={{ display: 'flex', alignItems: 'center', margin: '20px 0', opacity: 0.3 }}>
          <div style={{ flex: 1, height: '1px', background: '#94a3b8' }}></div>
          <span style={{ padding: '0 10px', fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Security</span>
          <div style={{ flex: 1, height: '1px', background: '#94a3b8' }}></div>
        </div>

        {/* Security / Domain info */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontSize: '11px', color: '#64748b' }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
          <span>Protected via Google Cloud & Enterprise SSO</span>
        </div>
      </div>
    </div>
  );
}
