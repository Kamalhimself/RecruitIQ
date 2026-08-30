import { useState, useEffect } from 'react';
import { API_BASE } from './config/api';
import Sidebar from './components/layout/Sidebar';
import AlertBanner from './components/layout/AlertBanner';
import CompaniesPanel from './components/companies/CompaniesPanel';
import JdsPanel from './components/jds/JdsPanel';
import MatchingPanel from './components/matching/MatchingPanel';

function App() {
  const [theme, setTheme] = useState('dark');
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

  // Fetch initial data
  const fetchClients = async () => {
    try {
      const res = await fetch(`${API_BASE}/clients`);
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
    fetchClients();
    fetchJds();
  }, []);

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
