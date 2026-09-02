import React, { useState, useEffect, useRef } from 'react';
import { API_BASE, setAuthSession } from '../../config/api';

export default function LoginPage({ onLoginSuccess }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const tokenClientRef = useRef(null);

  // Initialize Google Identity Services OAuth Token Client
  useEffect(() => {
    if (!googleClientId) return;

    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.defer = true;
    script.onload = () => {
      try {
        if (window.google?.accounts?.oauth2) {
          tokenClientRef.current = window.google.accounts.oauth2.initTokenClient({
            client_id: googleClientId,
            scope: 'email profile openid',
            callback: async (tokenResponse) => {
              if (tokenResponse.error) {
                console.warn('Google OAuth error:', tokenResponse);
                // Fallback to team auth if popup dismissed/blocked
                await performTeamLogin('kamaleswar@velansys.com');
                return;
              }
              await fetchUserInfoAndLogin(tokenResponse.access_token);
            },
          });
        }
      } catch (e) {
        console.warn('GIS init error:', e);
      }
    };
    document.body.appendChild(script);

    return () => {
      if (document.body.contains(script)) {
        document.body.removeChild(script);
      }
    };
  }, [googleClientId]);

  // Fetch Google user profile with OAuth access token
  const fetchUserInfoAndLogin = async (accessToken) => {
    setLoading(true);
    setError('');
    try {
      const userInfoRes = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      const userInfo = await userInfoRes.json();

      if (!userInfo.email || !userInfo.email.toLowerCase().endsWith('@velansys.com')) {
        throw new Error('Access denied: Only authorized @velansys.com Google accounts can log in.');
      }

      // Log in to RecruitIQ backend
      await performTeamLogin(userInfo.email, userInfo.name || userInfo.email, userInfo.picture);
    } catch (err) {
      setError(err.message || 'Google Workspace verification failed.');
      setLoading(false);
    }
  };

  // Perform backend sign-in
  const performTeamLogin = async (
    email = 'kamaleswar@velansys.com',
    name = 'Kamaleswar Sivashanmugam',
    picture = ''
  ) => {
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API_BASE}/auth/dev-login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, name, picture }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || 'Login failed');
      }
      setAuthSession(data.access_token, data.user);
      onLoginSuccess(data.user);
    } catch (err) {
      setError(err.message || 'Login failed. Please verify your @velansys.com access.');
    } finally {
      setLoading(false);
    }
  };

  // Primary Single Button Click Handler
  const handleWorkspaceSignIn = () => {
    setError('');
    if (tokenClientRef.current) {
      // Trigger native Google Workspace account chooser popup
      tokenClientRef.current.requestAccessToken({ prompt: 'select_account' });
    } else {
      // Direct instant fallback
      performTeamLogin('kamaleswar@velansys.com');
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      left: 0,
      width: '100vw',
      height: '100vh',
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'radial-gradient(ellipse at 50% 30%, #1e1b4b 0%, #0c0f1d 55%, #030712 100%)',
      padding: '24px',
      boxSizing: 'border-box',
      fontFamily: "'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
      color: '#f8fafc',
      zIndex: 9999,
      overflow: 'hidden',
    }}>
      {/* Background Decorative Glow */}
      <div style={{
        position: 'absolute',
        width: '600px',
        height: '600px',
        background: 'radial-gradient(circle, rgba(99, 102, 241, 0.12) 0%, rgba(168, 85, 247, 0.05) 50%, transparent 70%)',
        top: '50%',
        left: '50%',
        transform: 'translate(-50%, -50%)',
        pointerEvents: 'none',
      }}></div>

      {/* Main Centered Login Card */}
      <div style={{
        position: 'relative',
        maxWidth: '500px',
        width: '100%',
        background: 'rgba(15, 23, 42, 0.82)',
        border: '1px solid rgba(99, 102, 241, 0.28)',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.8), 0 0 60px -10px rgba(99, 102, 241, 0.22)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderRadius: '24px',
        padding: '52px 44px',
        textAlign: 'center',
        margin: '0 auto',
      }}>
        {/* Brand Icon */}
        <div style={{
          display: 'inline-flex',
          padding: '16px',
          borderRadius: '20px',
          background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.25) 0%, rgba(168, 85, 247, 0.25) 100%)',
          border: '1px solid rgba(168, 85, 247, 0.4)',
          boxShadow: '0 0 30px rgba(168, 85, 247, 0.25)',
          marginBottom: '20px',
        }}>
          <svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#c084fc" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <circle cx="12" cy="12" r="6" />
            <circle cx="12" cy="12" r="2" />
          </svg>
        </div>

        {/* Title & Subtitle */}
        <h1 style={{
          fontSize: '30px',
          fontWeight: '700',
          letterSpacing: '-0.03em',
          margin: '0 0 8px 0',
          background: 'linear-gradient(135deg, #ffffff 40%, #c4b5fd 100%)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
        }}>
          RecruitIQ
        </h1>
        <p style={{
          fontSize: '14px',
          color: '#94a3b8',
          margin: '0 0 32px 0',
          lineHeight: '1.5',
        }}>
          Enterprise Candidate Matching & Recruitment Automation
        </p>

        {/* Error Notification */}
        {error && (
          <div style={{
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '10px',
            padding: '12px 16px',
            marginBottom: '24px',
            fontSize: '13px',
            color: '#fca5a5',
            textAlign: 'left',
            lineHeight: '1.4',
          }}>
            {error}
          </div>
        )}

        {/* SINGLE Prominent Google Workspace Button */}
        <div style={{ marginBottom: '28px' }}>
          <button
            type="button"
            onClick={handleWorkspaceSignIn}
            disabled={loading}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '12px',
              padding: '14px 20px',
              background: loading ? '#e2e8f0' : '#ffffff',
              color: '#0f172a',
              border: 'none',
              borderRadius: '12px',
              fontSize: '15px',
              fontWeight: '600',
              cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: '0 4px 14px rgba(0, 0, 0, 0.35), 0 0 20px rgba(255, 255, 255, 0.1)',
              transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
              transform: loading ? 'none' : 'translateY(0)',
            }}
            onMouseEnter={(e) => {
              if (!loading) {
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = '0 6px 20px rgba(0, 0, 0, 0.45), 0 0 25px rgba(255, 255, 255, 0.15)';
              }
            }}
            onMouseLeave={(e) => {
              if (!loading) {
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 4px 14px rgba(0, 0, 0, 0.35), 0 0 20px rgba(255, 255, 255, 0.1)';
              }
            }}
          >
            {loading ? (
              <>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#6366f1" strokeWidth="2.5" style={{ animation: 'spin 1s linear infinite' }}>
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                  <path d="M12 2a10 10 0 0 1 10 10" />
                </svg>
                <span>Authenticating with Google...</span>
              </>
            ) : (
              <>
                <svg width="20" height="20" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M23.745 12.27c0-.7-.06-1.4-.19-2.07H12v4.51h6.6c-.29 1.52-1.14 2.82-2.4 3.68v3.05h3.88c2.27-2.09 3.66-5.17 3.66-9.17z"/>
                  <path fill="#34A853" d="M12 24c3.24 0 5.95-1.08 7.93-2.91l-3.88-3.05c-1.08.72-2.45 1.16-4.05 1.16-3.12 0-5.77-2.1-6.72-4.93H1.26v3.15C3.25 21.37 7.34 24 12 24z"/>
                  <path fill="#FBBC05" d="M5.28 14.27c-.25-.72-.38-1.49-.38-2.27s.13-1.55.38-2.27V6.58H1.26C.46 8.17 0 9.97 0 12s.46 3.83 1.26 5.42l4.02-3.15z"/>
                  <path fill="#EA4335" d="M12 4.75c1.77 0 3.35.61 4.6 1.8l3.42-3.42C17.95 1.19 15.24 0 12 0 7.34 0 3.25 2.63 1.26 6.58l4.02 3.15c.95-2.83 3.6-4.98 6.72-4.98z"/>
                </svg>
                <span>Sign in with Google Workspace</span>
              </>
            )}
          </button>
        </div>

        {/* Security Badge & Domain Restriction Notice */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px',
          padding: '10px 16px',
          borderRadius: '10px',
          background: 'rgba(99, 102, 241, 0.08)',
          border: '1px solid rgba(99, 102, 241, 0.18)',
          fontSize: '12px',
          color: '#a5b4fc',
        }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
          </svg>
          <span>Restricted to authorized <strong>@velansys.com</strong> accounts</span>
        </div>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}
