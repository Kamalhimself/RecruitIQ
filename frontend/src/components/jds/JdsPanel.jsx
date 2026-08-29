import React, { useState, useEffect, useRef, useMemo } from 'react';
import { API_BASE } from '../../config/api';
import { formatDate } from '../../utils/formatters';

export default function JdsPanel({ jds, clients, onRefresh, setError, setSuccess, onSelectJd }) {
  const [showDrawer, setShowDrawer] = useState(false);
  const [selectedClientId, setSelectedClientId] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  
  // Search and Jump State
  const [searchQuery, setSearchQuery] = useState('');
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [highlightedJdId, setHighlightedJdId] = useState(null);
  const searchRef = useRef(null);

  // Edit JD State
  const [editingJd, setEditingJd] = useState(null);
  const [editRoleTitle, setEditRoleTitle] = useState('');
  const [editClientId, setEditClientId] = useState('');
  const [editRequiredSkills, setEditRequiredSkills] = useState('');
  const [editNiceToHaveSkills, setEditNiceToHaveSkills] = useState('');
  const [editExpMin, setEditExpMin] = useState('');
  const [editExpMax, setEditExpMax] = useState('');
  const [editNoticePeriod, setEditNoticePeriod] = useState('');
  const [editLocation, setEditLocation] = useState('');
  const [editStatus, setEditStatus] = useState('open');
  const [editLoading, setEditLoading] = useState(false);

  // Preview State
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (clients.length > 0 && !selectedClientId) {
      setSelectedClientId(clients[0].client_id.toString());
    }
  }, [clients]);

  const openEditJdModal = (jd) => {
    setEditingJd(jd);
    setEditRoleTitle(jd.role_title || '');
    setEditClientId(jd.client_id ? jd.client_id.toString() : (clients[0]?.client_id?.toString() || ''));
    setEditRequiredSkills(Array.isArray(jd.required_skills) ? jd.required_skills.join(', ') : (jd.required_skills || ''));
    setEditNiceToHaveSkills(Array.isArray(jd.nice_to_have_skills) ? jd.nice_to_have_skills.join(', ') : (jd.nice_to_have_skills || ''));
    setEditExpMin(jd.experience_min !== null && jd.experience_min !== undefined ? jd.experience_min : '');
    setEditExpMax(jd.experience_max !== null && jd.experience_max !== undefined ? jd.experience_max : '');
    setEditNoticePeriod(jd.notice_period_days !== null && jd.notice_period_days !== undefined ? jd.notice_period_days : '');
    setEditLocation(jd.location || '');
    setEditStatus(jd.jd_status || 'open');
  };

  const handleEditJdSubmit = async (e) => {
    e.preventDefault();
    if (!editRoleTitle.trim()) {
      setError('Role title is required');
      return;
    }
    setEditLoading(true);
    try {
      const formData = new FormData();
      formData.append('role_title', editRoleTitle);
      if (editClientId) formData.append('client_id', editClientId);
      formData.append('required_skills', editRequiredSkills);
      formData.append('nice_to_have_skills', editNiceToHaveSkills);
      if (editExpMin !== '') formData.append('experience_min', editExpMin);
      if (editExpMax !== '') formData.append('experience_max', editExpMax);
      if (editNoticePeriod !== '') formData.append('notice_period_days', editNoticePeriod);
      formData.append('location', editLocation);
      formData.append('jd_status', editStatus);

      const res = await fetch(`${API_BASE}/jds/${editingJd.jd_id}`, {
        method: 'PUT',
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: 'Failed to update job description' }));
        throw new Error(detail.detail || 'Server error');
      }

      setSuccess(`Job Specification "${editingJd.jd_code}" updated successfully!`);
      setEditingJd(null);
      onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setEditLoading(false);
    }
  };

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

  // Compute matching company suggestions from JDs
  const companySuggestions = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase().trim();
    
    const companyMap = new Map();
    jds.forEach(jd => {
      const cName = jd.client_name || 'Acme Tech Solutions';
      const matchesCompany = cName.toLowerCase().includes(q);
      const matchesRole = jd.role_title && jd.role_title.toLowerCase().includes(q);
      const matchesCode = jd.jd_code && jd.jd_code.toLowerCase().includes(q);

      if (matchesCompany || matchesRole || matchesCode) {
        if (!companyMap.has(cName)) {
          companyMap.set(cName, []);
        }
        companyMap.get(cName).push(jd);
      }
    });

    return Array.from(companyMap.entries()).map(([cName, matchedJds]) => ({
      companyName: cName,
      jds: matchedJds,
      firstJdId: matchedJds[0]?.jd_id
    }));
  }, [searchQuery, jds]);

  const handleSelectCompany = (companyName, firstJdId) => {
    setSearchQuery(companyName);
    setIsDropdownOpen(false);
    
    const targetJdId = firstJdId || jds.find(j => (j.client_name || '').toLowerCase() === companyName.toLowerCase())?.jd_id;
    
    if (targetJdId) {
      setHighlightedJdId(targetJdId);
      
      setTimeout(() => {
        const rowEl = document.getElementById(`jd-row-${targetJdId}`);
        if (rowEl) {
          rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
      }, 50);

      setTimeout(() => {
        setHighlightedJdId(null);
      }, 3500);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      setSelectedFile(e.target.files[0]);
      setPreviewData(null);
    }
  };

  const handleRunPreview = async () => {
    if (!selectedFile) {
      setError('Please select a file to parse first.');
      return;
    }
    setIsPreviewing(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      
      const res = await fetch(`${API_BASE}/jds/parse`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) throw new Error('LLM Ingestion parsing failed.');
      const data = await res.json();
      setPreviewData(data);
      setSuccess('LLM Ingestion completed successfully! Review fields below.');
    } catch (err) {
      setError(err.message);
    } finally {
      setIsPreviewing(false);
    }
  };

  const handleSaveJd = async () => {
    if (!selectedFile || !selectedClientId) {
      setError('Client company and file are required.');
      return;
    }
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('client_id', selectedClientId);
      formData.append('created_by', '1');

      const res = await fetch(`${API_BASE}/jds`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const details = await res.json().catch(() => ({ detail: 'Failed to create job description' }));
        throw new Error(details.detail || 'Server error');
      }

      const data = await res.json();
      setSuccess(`Job Description "${data.role_title}" created with Code ${data.jd_code}!`);
      
      setSelectedFile(null);
      setPreviewData(null);
      setShowDrawer(false);
      onRefresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="header-section">
        <div className="header-title">
          <h1>Job Descriptions (JDs)</h1>
          <p>Parse, index, and organize role specifications</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowDrawer(true)}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          Ingest JD File
        </button>
      </div>

      <div className="card">
        <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <h2 className="card-title">Indexed Specifications ({jds.length})</h2>

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

            {isDropdownOpen && companySuggestions.length > 0 && (
              <div className="search-dropdown">
                {companySuggestions.map((item, idx) => (
                  <div 
                    key={idx} 
                    className="search-dropdown-item"
                    onClick={() => handleSelectCompany(item.companyName, item.firstJdId)}
                  >
                    <div className="search-item-company">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                      </svg>
                      <span>{item.companyName}</span>
                    </div>
                    <span className="search-item-count">
                      {item.jds.length} {item.jds.length === 1 ? 'spec' : 'specs'}
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
                <th>Code</th>
                <th>Role Title</th>
                <th>Client Company</th>
                <th>Experience (Min-Max)</th>
                <th>Notice Period</th>
                <th>Location</th>
                <th>Status</th>
                <th>Created On</th>
                <th>Modified On</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {jds.length === 0 ? (
                <tr>
                  <td colSpan="10" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px' }}>
                    No job descriptions found. Use "Ingest JD File" to run LLM extraction and save records.
                  </td>
                </tr>
              ) : (
                jds.map((jd) => {
                  const isHighlighted = highlightedJdId === jd.jd_id;
                  return (
                    <tr 
                      key={jd.jd_id} 
                      id={`jd-row-${jd.jd_id}`}
                      className={isHighlighted ? 'row-highlighted' : ''}
                    >
                      <td style={{ fontFamily: 'var(--font-mono)', fontSize: '13px', color: 'var(--color-primary)', fontWeight: '600', whiteSpace: 'nowrap' }}>
                        {jd.jd_code}
                      </td>
                      <td style={{ fontWeight: '600' }}>{jd.role_title}</td>
                      <td>{jd.client_name || 'Acme Tech Solutions'}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {jd.experience_min !== null && jd.experience_max !== null
                          ? `${jd.experience_min} - ${jd.experience_max} Years`
                          : 'Not specified'}
                      </td>
                      <td style={{ whiteSpace: 'nowrap' }}>{jd.notice_period_days !== null ? `${jd.notice_period_days} Days` : 'Immediate'}</td>
                      <td style={{ maxWidth: '180px' }}>
                        <span 
                          className="tag" 
                          style={{ 
                            display: 'inline-block', 
                            maxWidth: '100%', 
                            overflow: 'hidden', 
                            textOverflow: 'ellipsis', 
                            whiteSpace: 'nowrap',
                            verticalAlign: 'middle'
                          }} 
                          title={jd.location || 'Anywhere'}
                        >
                          {jd.location || 'Anywhere'}
                        </span>
                      </td>
                      <td>
                        <span className={`status-pill ${jd.jd_status || 'open'}`}>
                          {jd.jd_status || 'open'}
                        </span>
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(jd.created_at)}
                      </td>
                      <td style={{ fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                        {formatDate(jd.updated_at)}
                      </td>
                      <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', justifyContent: 'flex-end' }}>
                          <button 
                            className="btn-icon" 
                            title="Edit Job Description Details"
                            onClick={() => openEditJdModal(jd)}
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <circle cx="12" cy="12" r="3"></circle>
                              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                            </svg>
                          </button>
                          <button 
                            className="btn btn-secondary btn-sm" 
                            style={{ whiteSpace: 'nowrap' }}
                            onClick={() => onSelectJd(jd.jd_id)}
                          >
                            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                            Find Candidates
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add JD / Parsing Drawer */}
      {showDrawer && (
        <div className="modal-overlay" onClick={() => setShowDrawer(false)}>
          <div className="modal-content" style={{ width: '650px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="card-title">Ingest Job Specification</h2>
              <button className="close-btn" onClick={() => setShowDrawer(false)}>×</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="form-group">
                <label>Associate Client Company *</label>
                <select 
                  className="select"
                  value={selectedClientId}
                  onChange={(e) => setSelectedClientId(e.target.value)}
                  disabled={loading || isPreviewing}
                >
                  {clients.map((c) => (
                    <option key={c.client_id} value={c.client_id}>
                      {c.client_name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label>Job Description Document (PDF/DOCX) *</label>
                <div 
                  className="file-upload-container"
                  onClick={() => document.getElementById('jd-file-input').click()}
                >
                  <input 
                    type="file" 
                    id="jd-file-input" 
                    style={{ display: 'none' }} 
                    accept=".pdf,.docx,.doc,.txt"
                    onChange={handleFileChange}
                    disabled={loading || isPreviewing}
                  />
                  <div className="file-upload-icon">📂</div>
                  <div className="file-upload-text">
                    {selectedFile ? (
                      <strong>Selected: {selectedFile.name}</strong>
                    ) : (
                      <span>Click to upload or <span>browse files</span></span>
                    )}
                  </div>
                  <div className="file-upload-subtext">Supported formats: PDF, DOCX, TXT (Max 10MB)</div>
                </div>
              </div>

              {selectedFile && !previewData && (
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={handleRunPreview}
                  disabled={isPreviewing || loading}
                  style={{ width: '100%' }}
                >
                  {isPreviewing ? <><span className="spinner"></span> Running LLM Extractor...</> : '🚀 Run Ingestion Parse Preview'}
                </button>
              )}

              {/* Preview results */}
              {previewData && (
                <div className="parsed-preview-panel" style={{ animation: 'slideIn 0.25s ease' }}>
                  <div className="parsed-preview-header">
                    📊 LLM Extracted Structured Metadata
                  </div>
                  
                  <div className="grid-2">
                    <div className="parsed-field">
                      <span className="parsed-field-label">Role Title</span>
                      <span className="parsed-field-value" style={{ color: 'var(--color-primary)', fontWeight: '600' }}>
                        {previewData.parsed?.role_title || 'Unknown'}
                      </span>
                    </div>

                    <div className="parsed-field">
                      <span className="parsed-field-label">Notice Period Required</span>
                      <span className="parsed-field-value">
                        {previewData.parsed?.notice_period_days !== undefined ? `${previewData.parsed.notice_period_days} Days` : 'Immediate'}
                      </span>
                    </div>

                    <div className="parsed-field">
                      <span className="parsed-field-label">Experience Bracket</span>
                      <span className="parsed-field-value">
                        {previewData.parsed?.experience_min} - {previewData.parsed?.experience_max} Years
                      </span>
                    </div>

                    <div className="parsed-field">
                      <span className="parsed-field-label">Location Preference</span>
                      <span className="parsed-field-value">
                        {previewData.parsed?.location || 'Anywhere'}
                      </span>
                    </div>
                  </div>

                  <div className="parsed-field">
                    <span className="parsed-field-label">Required Core Skills</span>
                    <div className="tags-list" style={{ marginTop: '4px' }}>
                      {previewData.parsed?.required_skills?.map((s, idx) => (
                        <span key={idx} className="tag primary">{s}</span>
                      ))}
                    </div>
                  </div>

                  {previewData.parsed?.nice_to_have_skills && previewData.parsed.nice_to_have_skills.length > 0 && (
                    <div className="parsed-field">
                      <span className="parsed-field-label">Nice to Have Skills</span>
                      <div className="tags-list" style={{ marginTop: '4px' }}>
                        {previewData.parsed.nice_to_have_skills.map((s, idx) => (
                          <span key={idx} className="tag">{s}</span>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="parsed-field">
                    <span className="parsed-field-label">Raw Text Ingestion Clip</span>
                    <pre style={{ 
                      fontSize: '11px', 
                      background: 'rgba(0,0,0,0.3)', 
                      padding: '8px', 
                      borderRadius: '4px',
                      fontFamily: 'var(--font-mono)',
                      whiteSpace: 'pre-wrap',
                      maxHeight: '80px',
                      overflowY: 'auto',
                      color: 'var(--text-muted)'
                    }}>
                      {previewData.raw_text_preview}...
                    </pre>
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button 
                  type="button" 
                  className="btn btn-primary" 
                  style={{ flex: 1 }} 
                  disabled={loading || isPreviewing || !selectedFile}
                  onClick={handleSaveJd}
                >
                  {loading ? <span className="spinner"></span> : 'Commit & Save Job Description'}
                </button>
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={() => setShowDrawer(false)} 
                  disabled={loading || isPreviewing}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Edit JD Modal */}
      {editingJd && (
        <div className="modal-overlay" onClick={() => setEditingJd(null)}>
          <div className="modal-content" style={{ width: '680px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="card-title">Edit Job Specification ({editingJd.jd_code})</h2>
              <button className="close-btn" onClick={() => setEditingJd(null)}>×</button>
            </div>

            <form onSubmit={handleEditJdSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label>Role Title *</label>
                  <input 
                    type="text" 
                    className="input-text" 
                    value={editRoleTitle}
                    onChange={(e) => setEditRoleTitle(e.target.value)}
                    disabled={editLoading}
                  />
                </div>

                <div className="form-group">
                  <label>Associated Client Company</label>
                  <select 
                    className="select"
                    value={editClientId}
                    onChange={(e) => setEditClientId(e.target.value)}
                    disabled={editLoading}
                  >
                    {clients.map(c => (
                      <option key={c.client_id} value={c.client_id}>
                        {c.client_name} (#{c.client_id})
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label>Location</label>
                  <input 
                    type="text" 
                    className="input-text" 
                    placeholder="e.g. Chennai, India / Remote"
                    value={editLocation}
                    onChange={(e) => setEditLocation(e.target.value)}
                    disabled={editLoading}
                  />
                </div>

                <div className="form-group">
                  <label>Status</label>
                  <select 
                    className="select"
                    value={editStatus}
                    onChange={(e) => setEditStatus(e.target.value)}
                    disabled={editLoading}
                  >
                    <option value="open">Open</option>
                    <option value="on_hold">On Hold</option>
                    <option value="closed">Closed</option>
                    <option value="filled">Filled</option>
                  </select>
                </div>
              </div>

              <div className="form-group">
                <label>Required Skills (comma separated)</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. python, fastapi, postgresql, docker"
                  value={editRequiredSkills}
                  onChange={(e) => setEditRequiredSkills(e.target.value)}
                  disabled={editLoading}
                />
              </div>

              <div className="form-group">
                <label>Nice-to-have Skills (comma separated)</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. aws, kubernetes, redis"
                  value={editNiceToHaveSkills}
                  onChange={(e) => setEditNiceToHaveSkills(e.target.value)}
                  disabled={editLoading}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '16px' }}>
                <div className="form-group">
                  <label>Min Experience (Yrs)</label>
                  <input 
                    type="number" 
                    step="0.5"
                    className="input-text" 
                    value={editExpMin}
                    onChange={(e) => setEditExpMin(e.target.value)}
                    disabled={editLoading}
                  />
                </div>

                <div className="form-group">
                  <label>Max Experience (Yrs)</label>
                  <input 
                    type="number" 
                    step="0.5"
                    className="input-text" 
                    value={editExpMax}
                    onChange={(e) => setEditExpMax(e.target.value)}
                    disabled={editLoading}
                  />
                </div>

                <div className="form-group">
                  <label>Notice Period (Days)</label>
                  <input 
                    type="number" 
                    className="input-text" 
                    value={editNoticePeriod}
                    onChange={(e) => setEditNoticePeriod(e.target.value)}
                    disabled={editLoading}
                  />
                </div>
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={editLoading}>
                  {editLoading ? <span className="spinner"></span> : 'Save Changes'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setEditingJd(null)} disabled={editLoading}>
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
