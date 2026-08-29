import React, { useState, useEffect, useRef, useMemo } from 'react';
import { API_BASE } from '../../config/api';
import { formatDate } from '../../utils/formatters';

export default function CompaniesPanel({ clients, onRefresh, setError, setSuccess }) {
  const [showDrawer, setShowDrawer] = useState(false);
  const [name, setName] = useState('');
  const [person, setPerson] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [createdBy, setCreatedBy] = useState('');
  const [loading, setLoading] = useState(false);

  // Search and Jump State
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [highlightedClientId, setHighlightedClientId] = useState(null);
  const searchRef = useRef(null);

  // Edit Modal State
  const [editingClient, setEditingClient] = useState(null);
  const [editName, setEditName] = useState('');
  const [editPerson, setEditPerson] = useState('');
  const [editEmail, setEditEmail] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editModifiedBy, setEditModifiedBy] = useState('');
  const [editLoading, setEditLoading] = useState(false);

  // Close dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Compute matching company suggestions
  const clientSuggestions = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase().trim();
    
    return clients.filter(c => 
      (c.client_name && c.client_name.toLowerCase().includes(q)) ||
      (c.contact_person && c.contact_person.toLowerCase().includes(q)) ||
      (c.contact_email && c.contact_email.toLowerCase().includes(q)) ||
      (c.contact_phone && c.contact_phone.toLowerCase().includes(q)) ||
      c.client_id.toString().includes(q)
    );
  }, [searchQuery, clients]);

  const handleSelectClient = (client) => {
    setSearchQuery(client.client_name);
    setIsDropdownOpen(false);
    
    const targetId = client.client_id;
    setHighlightedClientId(targetId);
    
    setTimeout(() => {
      const rowEl = document.getElementById(`company-row-${targetId}`);
      if (rowEl) {
        rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 50);

    setTimeout(() => {
      setHighlightedClientId(null);
    }, 3500);
  };

  const handleCreateSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) {
      setError('Company name is required');
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('client_name', name);
      formData.append('contact_person', person);
      formData.append('contact_email', email);
      formData.append('contact_phone', phone);
      formData.append('created_by', createdBy);

      const res = await fetch(`${API_BASE}/clients`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: 'Failed to create client' }));
        throw new Error(detail.detail || 'Server error');
      }

      setSuccess(`Company "${name}" registered successfully!`);
      setName('');
      setPerson('');
      setEmail('');
      setPhone('');
      setCreatedBy('');
      setShowDrawer(false);
      onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const openEditModal = (client) => {
    setEditingClient(client);
    setEditName(client.client_name || '');
    setEditPerson(client.contact_person || '');
    setEditEmail(client.contact_email || '');
    setEditPhone(client.contact_phone || '');
    setEditModifiedBy(client.modified_by || '');
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!editName.trim()) {
      setError('Company name is required');
      return;
    }
    setEditLoading(true);
    try {
      const formData = new FormData();
      formData.append('client_name', editName);
      formData.append('contact_person', editPerson);
      formData.append('contact_email', editEmail);
      formData.append('contact_phone', editPhone);
      formData.append('modified_by', editModifiedBy);

      const res = await fetch(`${API_BASE}/clients/${editingClient.client_id}`, {
        method: 'PUT',
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: 'Failed to update client' }));
        throw new Error(detail.detail || 'Server error');
      }

      setSuccess(`Company "${editName}" updated successfully!`);
      setEditingClient(null);
      onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setEditLoading(false);
    }
  };

  return (
    <>
      <div className="header-section">
        <div className="header-title">
          <h1>Companies Dashboard</h1>
          <p>Register and manage client organizations</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowDrawer(true)}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add Company
        </button>
      </div>

      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <h2 className="card-title">All Clients ({clients.length})</h2>

          {/* Company Search Bar */}
          <div className="search-bar-container" ref={searchRef}>
            <div className="search-input-wrapper">
              <svg className="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"></circle>
                <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
              </svg>
              <input 
                type="text"
                className="input-text"
                placeholder="Search company & jump to table..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setIsDropdownOpen(true);
                }}
                onFocus={() => {
                  if (searchQuery.trim()) setIsDropdownOpen(true);
                }}
              />
              {searchQuery && (
                <button 
                  type="button" 
                  className="search-clear-btn" 
                  onClick={() => {
                    setSearchQuery('');
                    setIsDropdownOpen(false);
                  }}
                  title="Clear search"
                >
                  ✕
                </button>
              )}
            </div>

            {isDropdownOpen && clientSuggestions.length > 0 && (
              <div className="search-dropdown">
                {clientSuggestions.map((c) => (
                  <div 
                    key={c.client_id} 
                    className="search-dropdown-item"
                    onClick={() => handleSelectClient(c)}
                  >
                    <div className="search-item-company">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                      </svg>
                      <span>{c.client_name}</span>
                    </div>
                    <span className="search-item-count">
                      {c.contact_person || `#${c.client_id}`}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
        
        <div className="table-container">
          <table className="premium-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Company Name</th>
                <th>Contact Person</th>
                <th>Email Address</th>
                <th>Phone Number</th>
                <th>Created By</th>
                <th>Created On</th>
                <th>Modified By</th>
                <th>Modified On</th>
                <th style={{ textAlign: 'center' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {clients.length === 0 ? (
                <tr>
                  <td colSpan="10" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px' }}>
                    No companies registered yet. Click "Add Company" to get started.
                  </td>
                </tr>
              ) : (
                clients.map((c) => {
                  const isHighlighted = highlightedClientId === c.client_id;
                  return (
                    <tr 
                      key={c.client_id}
                      id={`company-row-${c.client_id}`}
                      className={isHighlighted ? 'row-highlighted' : ''}
                    >
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--color-primary)' }}>
                        #{c.client_id}
                      </td>
                      <td style={{ fontWeight: '600' }}>{c.client_name}</td>
                      <td>{c.contact_person || '—'}</td>
                      <td style={{ color: 'var(--text-muted)' }}>{c.contact_email || '—'}</td>
                      <td>{c.contact_phone || '—'}</td>
                      <td>
                        <span className="badge badge-neutral" style={{ fontSize: '12px' }}>
                          {c.created_by || '—'}
                        </span>
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(c.created_at)}
                      </td>
                      <td>
                        <span className="badge badge-neutral" style={{ fontSize: '12px' }}>
                          {c.modified_by || '—'}
                        </span>
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(c.updated_at)}
                      </td>
                      <td style={{ textAlign: 'center' }}>
                        <button 
                          className="btn-icon" 
                          title="Edit Company Details"
                          onClick={() => openEditModal(c)}
                        >
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <circle cx="12" cy="12" r="3"></circle>
                            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                          </svg>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Client Drawer */}
      {showDrawer && (
        <div className="modal-overlay" onClick={() => setShowDrawer(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="card-title">Register Company</h2>
              <button className="close-btn" onClick={() => setShowDrawer(false)}>×</button>
            </div>
            
            <form onSubmit={handleCreateSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="form-group">
                <label>Company Name *</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. Acme Tech Solutions"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Contact Person</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. Priya Sharma"
                  value={person}
                  onChange={(e) => setPerson(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Email Address</label>
                <input 
                  type="email" 
                  className="input-text" 
                  placeholder="e.g. priya@acmetech.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Phone Number</label>
                <input 
                  type="tel" 
                  className="input-text" 
                  placeholder="e.g. +91 98765 43210"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div className="form-group">
                <label>Created By</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. Admin / Kamal"
                  value={createdBy}
                  onChange={(e) => setCreatedBy(e.target.value)}
                  disabled={loading}
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={loading}>
                  {loading ? <span className="spinner"></span> : 'Submit Registration'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowDrawer(false)} disabled={loading}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Client Modal */}
      {editingClient && (
        <div className="modal-overlay" onClick={() => setEditingClient(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="card-title">Edit Company Details (#{editingClient.client_id})</h2>
              <button className="close-btn" onClick={() => setEditingClient(null)}>×</button>
            </div>
            
            <form onSubmit={handleEditSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div className="form-group">
                <label>Company Name *</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. Acme Tech Solutions"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  disabled={editLoading}
                />
              </div>

              <div className="form-group">
                <label>Contact Person</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. Priya Sharma"
                  value={editPerson}
                  onChange={(e) => setEditPerson(e.target.value)}
                  disabled={editLoading}
                />
              </div>

              <div className="form-group">
                <label>Email Address</label>
                <input 
                  type="email" 
                  className="input-text" 
                  placeholder="e.g. priya@acmetech.com"
                  value={editEmail}
                  onChange={(e) => setEditEmail(e.target.value)}
                  disabled={editLoading}
                />
              </div>

              <div className="form-group">
                <label>Phone Number</label>
                <input 
                  type="tel" 
                  className="input-text" 
                  placeholder="e.g. +91 98765 43210"
                  value={editPhone}
                  onChange={(e) => setEditPhone(e.target.value)}
                  disabled={editLoading}
                />
              </div>

              <div className="form-group">
                <label>Modified By (Editor)</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. Admin / Kamal"
                  value={editModifiedBy}
                  onChange={(e) => setEditModifiedBy(e.target.value)}
                  disabled={editLoading}
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={editLoading}>
                  {editLoading ? <span className="spinner"></span> : 'Save Changes'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setEditingClient(null)} disabled={editLoading}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
