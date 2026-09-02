import { useState, useEffect } from 'react';
import { API_BASE, getAuthUser, clearAuthSession } from './config/api';
import Sidebar from './components/layout/Sidebar';
import AlertBanner from './components/layout/AlertBanner';
import CompaniesPanel from './components/companies/CompaniesPanel';
import JdsPanel from './components/jds/JdsPanel';
import MatchingPanel from './components/matching/MatchingPanel';
import LoginPage from './components/auth/LoginPage';

function App() {
  const [theme, setTheme] = useState('dark');
  const [currentUser, setCurrentUser] = useState(() => getAuthUser());
  const [activeTab, setActiveTab] = useState('clients');
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [clients, setClients] = useState([]);
  const [jds, setJds] = useState([]);
  const [selectedJdId, setSelectedJdId] = useState('');
  
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Sync theme attribute
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Listen for unauthorized session expiration
  useEffect(() => {
    const handleUnauthorized = () => {
      setCurrentUser(null);
      setError('Your session has expired or requires authentication. Please sign in again.');
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, []);

  // Auto-clear messages
  useEffect(() => {
    if (success) {
      const timer = setTimeout(() => setSuccess(''), 5000);
      return () => clearTimeout(timer);
    }
  }, [success]);

  useEffect(() => {
    if (error) {
      const timer = setTimeout(() => setError(''), 8000);
      return () => clearTimeout(timer);
    }
  }, [error]);

  // Fetch initial data once authenticated
  const fetchClients = async () => {
    try {
      const res = await fetch(`${API_BASE}/clients`);
      if (res.status === 401) return;
      if (!res.ok) throw new Error('Failed to fetch clients');
      const data = await res.json();
      setClients(data);
    } catch (err) {
      console.error(err);
      setError('Could not connect to backend server. Make sure FastAPI is running.');
    }
  };

  const fetchJds = async () => {
    try {
      const res = await fetch(`${API_BASE}/jds`);
      if (res.status === 401) return;
      if (!res.ok) throw new Error('Failed to fetch JDs');
      const data = await res.json();
      setJds(data);
      if (data.length > 0 && !selectedJdId) {
        setSelectedJdId(data[0].jd_id.toString());
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    if (currentUser) {
      fetchClients();
      fetchJds();
    }
  }, [currentUser]);

  const handleLogout = () => {
    clearAuthSession();
    setCurrentUser(null);
    setClients([]);
    setJds([]);
    setSelectedJdId('');
  };

  // If not logged in, render the Google Workspace SSO Login Page
  if (!currentUser) {
    return (
      <LoginPage
        onLoginSuccess={(user) => {
          setCurrentUser(user);
          setSuccess(`Welcome back, ${user.name || user.email}!`);
        }}
      />
    );
  }

  return (
    <div className="app-layout">
      {/* Sidebar Navigation */}
      <Sidebar 
        theme={theme}
        setTheme={setTheme}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        isSidebarCollapsed={isSidebarCollapsed}
        setIsSidebarCollapsed={setIsSidebarCollapsed}
        currentUser={currentUser}
        onLogout={handleLogout}
      />

      {/* Main Panel Content */}
      <main className={`main-content ${isSidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
        {/* Global Toast Notifications */}
        <AlertBanner 
          error={error} 
          success={success} 
          onCloseError={() => setError('')}
          onCloseSuccess={() => setSuccess('')}
        />

        {/* Tab Components */}
        {activeTab === 'clients' && (
          <CompaniesPanel 
            clients={clients} 
            onRefresh={fetchClients} 
            setError={setError} 
            setSuccess={setSuccess} 
          />
        )}
        
        {activeTab === 'jds' && (
          <JdsPanel 
            jds={jds} 
            clients={clients} 
            onRefresh={fetchJds} 
            setError={setError} 
            setSuccess={setSuccess}
            onSelectJd={(jdId) => {
              setSelectedJdId(jdId.toString());
              setActiveTab('matching');
            }}
          />
        )}

        {activeTab === 'matching' && (
          <MatchingPanel 
            jds={jds} 
            clients={clients} 
            selectedJdId={selectedJdId} 
            setSelectedJdId={setSelectedJdId} 
            setError={setError} 
            setSuccess={setSuccess}
          />
        )}
      </main>
    </div>
  );
}

export default App;
