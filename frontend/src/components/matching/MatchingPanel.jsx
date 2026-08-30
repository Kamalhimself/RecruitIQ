import React, { useState, useEffect, useMemo } from 'react';
import { API_BASE } from '../../config/api';

export default function MatchingPanel({ jds, selectedJdId, setSelectedJdId, setError, setSuccess }) {
  const [mappings, setMappings] = useState([]);
  const [jdDetails, setJdDetails] = useState(null);
  
  // Configs
  const [threshold, setThreshold] = useState(70);
  const [wSkills, setWSkills] = useState(40);
  const [wExp, setWExp] = useState(25);
  const [wNotice, setWNotice] = useState(20);
  const [wLoc, setWLoc] = useState(15);
  const [showWeightsConfig, setShowWeightsConfig] = useState(false);

  // Targeted / Selected Candidate Matching State
  const [allCandidates, setAllCandidates] = useState([]);
  const [showCandidatePicker, setShowCandidatePicker] = useState(false);
  const [selectedCandidateCodes, setSelectedCandidateCodes] = useState([]);
  const [candidateSearchTerm, setCandidateSearchTerm] = useState('');
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [pickerJdId, setPickerJdId] = useState('');
  
  // Upload States
  const [showUploadDrawer, setShowUploadDrawer] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [source, setSource] = useState('manual_upload');
  const [sourceDetail, setSourceDetail] = useState('');
  const [isUploading, setIsUploading] = useState(false);

  // Active Selection Filter (null = show all for JD, array = show only selected CVs)
  const [activeSelectionFilter, setActiveSelectionFilter] = useState(null);

  // States for loaders
  const [loading, setLoading] = useState(false);
  const [runningMatch, setRunningMatch] = useState(false);

  // Bulk Email States
  const [isBulkSending, setIsBulkSending] = useState(false);
  const [bulkProgress, setBulkProgress] = useState({ current: 0, total: 0 });

  // Get active JD object
  const activeJd = jds.find(j => j.jd_id.toString() === selectedJdId);

  const fetchMappings = async (jdId) => {
    if (!jdId) return [];
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/matching/jds/${jdId}`);
      if (!res.ok) throw new Error('Failed to fetch candidate scores.');
      const data = await res.json();
      setMappings(data);
      return data;
    } catch (err) {
      setError(err.message);
      return [];
    } finally {
      setLoading(false);
    }
  };

  const fetchCandidatePool = async (jdId) => {
    const targetId = jdId || pickerJdId || selectedJdId;
    if (!targetId) return;
    setLoadingCandidates(true);
    try {
      const res = await fetch(`${API_BASE}/candidates?jd_id=${targetId}&direct_only=true&limit=200`);
      if (res.ok) {
        const data = await res.json();
        const items = data.items || [];
        setAllCandidates(items);
        // Pre-select all CVs for this JD by default
        setSelectedCandidateCodes(items.map(c => c.candidate_code));
      }
    } catch (err) {
      console.error('Failed to load candidates', err);
    } finally {
      setLoadingCandidates(false);
    }
  };

  useEffect(() => {
    if (selectedJdId) {
      fetchMappings(selectedJdId);
    }
  }, [selectedJdId]);

  const filteredCandidates = useMemo(() => {
    if (!candidateSearchTerm.trim()) return allCandidates;
    const term = candidateSearchTerm.toLowerCase().trim();
    return allCandidates.filter(c => 
      (c.full_name && c.full_name.toLowerCase().includes(term)) ||
      (c.candidate_code && c.candidate_code.toLowerCase().includes(term)) ||
      (c.current_location && c.current_location.toLowerCase().includes(term)) ||
      (c.skills && c.skills.some(s => s.toLowerCase().includes(term)))
    );
  }, [allCandidates, candidateSearchTerm]);

  // Compute displayed mappings based on whether selected CVs filter is active
  const displayedMappings = useMemo(() => {
    if (!activeSelectionFilter || activeSelectionFilter.length === 0) {
      return mappings;
    }
    const filterSet = new Set(activeSelectionFilter);
    return mappings.filter(m => filterSet.has(m.candidate_code));
  }, [mappings, activeSelectionFilter]);

  const handleRunMatching = async () => {
    if (!selectedJdId) return;
    setRunningMatch(true);
    setActiveSelectionFilter(null); // Clear filter to show full pool
    try {
      const res = await fetch(`${API_BASE}/matching/jds/${selectedJdId}/run?shortlist_threshold=${threshold}&w_skills=${wSkills}&w_experience=${wExp}&w_notice=${wNotice}&w_location=${wLoc}`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Error running candidate matching indexer.');
      const data = await res.json();
      
      setSuccess(`Completed semantic matching for ${data.matched} profiles in the full talent pool!`);
      await fetchMappings(selectedJdId);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningMatch(false);
    }
  };

  const handleRunMatchingForSelection = async (candidateCodesToRun, targetJdId, isSingleRescore = false) => {
    const jdId = targetJdId || pickerJdId || selectedJdId;
    if (!jdId) {
      setError('Please select a Job Description first.');
      return;
    }
    const codes = candidateCodesToRun || selectedCandidateCodes;
    if (!codes || codes.length === 0) {
      setError('Please select at least one candidate CV to run matching on.');
      return;
    }
    setRunningMatch(true);
    try {
      const res = await fetch(`${API_BASE}/matching/jds/${jdId}/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          candidate_codes: codes,
          shortlist_threshold: threshold,
          w_skills: wSkills,
          w_experience: wExp,
          w_notice: wNotice,
          w_location: wLoc,
        }),
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: 'Failed to run matching' }));
        throw new Error(detail.detail || 'Server error');
      }

      const data = await res.json();
      const targetJd = jds.find(j => j.jd_id.toString() === jdId.toString());
      setSuccess(`Completed semantic matching for ${data.matched} candidate CV(s) against "${targetJd?.role_title || jdId}"!`);
      setShowCandidatePicker(false);
      
      // Only set filter if this was triggered from the Selection modal (not when re-scoring a single row in existing view)
      if (!isSingleRescore) {
        setActiveSelectionFilter(codes);
      }

      if (jdId.toString() !== selectedJdId.toString()) {
        setSelectedJdId(jdId.toString());
      } else {
        await fetchMappings(jdId);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningMatch(false);
    }
  };

  const handleUploadCv = async (e) => {
    e.preventDefault();
    if (!uploadFile) {
      setError('Please select a resume file (PDF/DOCX).');
      return;
    }
    setIsUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('source', source);
      formData.append('jd_id', selectedJdId);
      formData.append('source_detail', sourceDetail);
      formData.append('uploaded_by', '1');

      const res = await fetch(`${API_BASE}/candidates`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        const detail = await res.json().catch(() => ({ detail: 'Upload error' }));
        throw new Error(detail.detail || 'Server error');
      }

      const data = await res.json();
      if (data.duplicate) {
        setSuccess(`Recognized existing candidate profile (${data.full_name}). Mapped to this JD!`);
      } else {
        setSuccess(`Ingested Candidate "${data.full_name}" successfully with code ${data.candidate_code}!`);
      }

      setUploadFile(null);
      setSourceDetail('');
      setShowUploadDrawer(false);
      handleRunMatching();
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  };

  const handleUpdateStatus = async (mappingId, newStatus) => {
    try {
      const res = await fetch(`${API_BASE}/workflow/mappings/${mappingId}/status/${newStatus}`, {
        method: 'POST',
      });
      if (!res.ok) throw new Error('Status update failed');
      
      setMappings(prev => prev.map(m => m.mapping_id === mappingId ? { ...m, status: newStatus } : m));
      setSuccess('Candidate recruitment status updated successfully.');
    } catch (err) {
      setError(err.message);
    }
  };

  const handleSendScreening = async (mappingId, candidateName) => {
    try {
      setSuccess(`Sending screening email to ${candidateName}...`);
      const res = await fetch(`${API_BASE}/workflow/mappings/${mappingId}/screening-email`, {
        method: 'POST',
      });
      if (!res.ok) {
        const details = await res.json().catch(() => ({ detail: 'Failed to send screening email' }));
        throw new Error(details.detail || 'Gmail client connection error.');
      }
      
      setMappings(prev => prev.map(m => m.mapping_id === mappingId ? { ...m, status: 'screening_sent' } : m));
      setSuccess(`Email screening questionnaire successfully dispatched to ${candidateName}!`);
    } catch (err) {
      setError(err.message);
    }
  };

  const getScoreClass = (score) => {
    if (score >= 80) return 'high';
    if (score >= 55) return 'medium';
    return 'low';
  };

  return (
    <>
      <div className="header-section">
        <div className="header-title">
          <h1>Candidate Matching Engine</h1>
          <p>Score resumes, review semantic matches, and dispatch screening questionnaires</p>
        </div>
        
        <div style={{ display: 'flex', gap: '12px' }}>
          <button 
            className="btn btn-secondary" 
            onClick={() => setShowUploadDrawer(true)}
            disabled={!selectedJdId}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
            Upload Candidate CV
          </button>
        </div>
      </div>

      <div className="card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', gap: '20px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ flex: 1, minWidth: '250px' }}>
            <label>Select Active Job Specification</label>
            <select 
              className="select"
              value={selectedJdId}
              onChange={(e) => {
                setActiveSelectionFilter(null);
                setSelectedJdId(e.target.value);
              }}
            >
              <option value="" disabled>-- Select a Job Description --</option>
              {jds.map((j) => (
                <option key={j.jd_id} value={j.jd_id}>
                  {j.jd_code} - {j.role_title} ({j.client_name || 'Client'})
                </option>
              ))}
            </select>
          </div>

          {activeJd && (
            <div style={{ display: 'flex', gap: '24px', flex: 2, paddingLeft: '20px', borderLeft: '1px solid var(--border-color)' }}>
              <div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Target Location</span>
                <p style={{ fontWeight: '600', fontSize: '15px', color: 'var(--text-main)' }}>{activeJd.location || 'Chennai'}</p>
              </div>
              <div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Notice Cap</span>
                <p style={{ fontWeight: '600', fontSize: '15px', color: 'var(--text-main)' }}>
                  {activeJd.notice_period_days !== null ? `${activeJd.notice_period_days} Days` : 'No Cap'}
                </p>
              </div>
              <div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)', textTransform: 'uppercase' }}>Core Skills required</span>
                <div className="tags-list" style={{ marginTop: '4px' }}>
                  {activeJd.required_skills?.map((s, idx) => (
                    <span key={idx} className="tag primary">{s}</span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {activeJd && (
        <>
          <div className="matching-config-bar">
            <div className="slider-container">
              <span className="slider-label">Shortlist score threshold:</span>
              <input 
                type="range" 
                className="range-input" 
                min="0" 
                max="100" 
                value={threshold} 
                onChange={(e) => setThreshold(parseInt(e.target.value))}
              />
              <span className="range-val-badge">{threshold}%</span>
            </div>

            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
              <button 
                type="button"
                className={`btn btn-secondary ${showWeightsConfig ? 'active' : ''}`}
                onClick={() => setShowWeightsConfig(prev => !prev)}
                title="Customize Scoring Weightage"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
                Weights
              </button>

              <button 
                type="button"
                className="btn btn-secondary"
                onClick={() => {
                  const targetId = selectedJdId || (jds[0]?.jd_id ? jds[0].jd_id.toString() : '');
                  setPickerJdId(targetId);
                  setShowCandidatePicker(true);
                  fetchCandidatePool(targetId);
                }}
                disabled={runningMatch || !selectedJdId}
                title="Choose specific CVs to match against a JD"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="9 11 12 14 22 4" />
                  <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                </svg>
                🎯 Match Selected CV(s)
              </button>

              <button 
                className="btn btn-primary" 
                onClick={handleRunMatching}
                disabled={runningMatch || loading}
              >
                {runningMatch ? (
                  <><span className="spinner"></span> Matching...</>
                ) : (
                  <>🚀 Match Full Pool</>
                )}
              </button>
            </div>
          </div>

          {showWeightsConfig && (
            <div className="card" style={{ padding: '24px', animation: 'slideIn 0.2s ease', backgroundColor: 'var(--bg-primary)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-color)', paddingBottom: '12px', marginBottom: '16px' }}>
                <h3 style={{ fontSize: '16px', fontWeight: '600' }}>Dynamic Criteria Weightage Customizer</h3>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>* Inputs automatically normalize to 100% total weightage</span>
              </div>
              <div className="grid-2" style={{ gap: '20px 40px' }}>
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: '500' }}>
                    <span>Skills Weightage</span>
                    <span style={{ color: 'var(--color-primary)', fontWeight: '700' }}>
                      {Math.round((wSkills / (wSkills + wExp + wNotice + wLoc || 1)) * 100)}% ({wSkills} pts)
                    </span>
                  </div>
                  <input 
                    type="range" 
                    className="range-input" 
                    min="0" 
                    max="100" 
                    value={wSkills} 
                    onChange={(e) => setWSkills(parseInt(e.target.value))}
                  />
                </div>
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: '500' }}>
                    <span>Experience Weightage</span>
                    <span style={{ color: 'var(--color-success)', fontWeight: '700' }}>
                      {Math.round((wExp / (wSkills + wExp + wNotice + wLoc || 1)) * 100)}% ({wExp} pts)
                    </span>
                  </div>
                  <input 
                    type="range" 
                    className="range-input" 
                    min="0" 
                    max="100" 
                    value={wExp} 
                    onChange={(e) => setWExp(parseInt(e.target.value))}
                  />
                </div>
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: '500' }}>
                    <span>Notice Period Weightage</span>
                    <span style={{ color: 'var(--color-warning)', fontWeight: '700' }}>
                      {Math.round((wNotice / (wSkills + wExp + wNotice + wLoc || 1)) * 100)}% ({wNotice} pts)
                    </span>
                  </div>
                  <input 
                    type="range" 
                    className="range-input" 
                    min="0" 
                    max="100" 
                    value={wNotice} 
                    onChange={(e) => setWNotice(parseInt(e.target.value))}
                  />
                </div>
                <div className="form-group">
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', fontWeight: '500' }}>
                    <span>Location Weightage</span>
                    <span style={{ color: 'var(--color-purple)', fontWeight: '700' }}>
                      {Math.round((wLoc / (wSkills + wExp + wNotice + wLoc || 1)) * 100)}% ({wLoc} pts)
                    </span>
                  </div>
                  <input 
                    type="range" 
                    className="range-input" 
                    min="0" 
                    max="100" 
                    value={wLoc} 
                    onChange={(e) => setWLoc(parseInt(e.target.value))}
                  />
                </div>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '12px', color: 'var(--text-muted)', borderTop: '1px solid var(--border-color)', paddingTop: '12px', marginTop: '16px' }}>
                <span>Sum total: {wSkills + wExp + wNotice + wLoc} pts</span>
                <button 
                  type="button" 
                  className="btn btn-secondary btn-sm"
                  style={{ padding: '4px 10px', fontSize: '11px' }}
                  onClick={() => {
                    setWSkills(40);
                    setWExp(25);
                    setWNotice(20);
                    setWLoc(15);
                  }}
                >
                  Reset Defaults
                </button>
              </div>
            </div>
          )}

          <div className="metrics-grid">
            <div className="metric-card">
              <span className="metric-title">
                {activeSelectionFilter ? 'Selected Profiles' : 'Matched Candidates'}
              </span>
              <span className="metric-value">{displayedMappings.length}</span>
              <span className="metric-desc">
                {activeSelectionFilter ? `Filtered from ${mappings.length} total` : 'Discovered resume matches'}
              </span>
            </div>

            <div className="metric-card success">
              <span className="metric-title">Shortlisted Profiles</span>
              <span className="metric-value">
                {displayedMappings.filter(m => m.status === 'shortlisted' || m.status === 'recruiter_approved' || m.status === 'screening_sent').length}
              </span>
              <span className="metric-desc">Score at or above {threshold}%</span>
            </div>

            <div className="metric-card purple">
              <span className="metric-title">Top Match Score</span>
              <span className="metric-value">
                {displayedMappings.length > 0 && displayedMappings[0].match_score !== null 
                  ? `${displayedMappings[0].match_score}%`
                  : '—'}
              </span>
              <span className="metric-desc">Semantic similarity maximum</span>
            </div>
          </div>

          {isBulkSending && (
            <div className="bulk-bar" style={{ animation: 'slideIn 0.3s ease' }}>
              <div className="progress-header">
                <span>📧 Despatching Screening Questionnaires...</span>
                <span>{bulkProgress.current} / {bulkProgress.total}</span>
              </div>
              <div className="progress-track">
                <div 
                  className="progress-fill" 
                  style={{ width: `${(bulkProgress.current / bulkProgress.total) * 100}%` }}
                ></div>
              </div>
            </div>
          )}

          <div className="card">
            <div className="card-header" style={{ borderBottom: 'none', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <h2 className="card-title">Indexed Matching Scores for {activeJd.role_title}</h2>
                {activeSelectionFilter && (
                  <span className="badge badge-neutral" style={{ color: 'var(--color-primary)', backgroundColor: 'var(--color-primary-glow)', fontSize: '12px', fontWeight: '600', padding: '4px 10px', borderRadius: '20px' }}>
                    🎯 Filtered: Showing {displayedMappings.length} Selected Profile(s)
                  </span>
                )}
              </div>

              {activeSelectionFilter && (
                <button 
                  type="button" 
                  className="btn btn-secondary btn-sm"
                  onClick={() => setActiveSelectionFilter(null)}
                  title="Clear filter and show all candidate match records for this JD"
                >
                  Show All Candidates ({mappings.length})
                </button>
              )}
            </div>

            <div className="table-container">
              <table className="premium-table">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Overall Score</th>
                    <th>Score Breakdown</th>
                    <th>Explanation</th>
                    <th>Workflow Status</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '60px' }}>
                        <span className="spinner spinner-lg"></span>
                        <p style={{ marginTop: '12px', color: 'var(--text-muted)' }}>Fetching candidate mapping files...</p>
                      </td>
                    </tr>
                  ) : displayedMappings.length === 0 ? (
                    <tr>
                      <td colSpan="6" style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                        {activeSelectionFilter 
                          ? 'No matching scores found for the selected candidate CVs. Try re-scoring them or click "Show All Candidates".'
                          : 'No candidates scored for this JD yet. Use "Match Selected CV(s)" or "Match Full Pool" to index and score candidates!'}
                      </td>
                    </tr>
                  ) : (
                    displayedMappings.map((m) => (
                      <tr key={m.mapping_id}>
                        <td>
                          <div style={{ fontWeight: '600' }}>{m.full_name}</div>
                          <div style={{ fontSize: '11px', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                            {m.candidate_code}
                          </div>
                        </td>
                        <td>
                          <div className="score-badge-container">
                            <span className={`score-badge ${getScoreClass(m.match_score)}`}>
                              {m.match_score !== null ? Math.round(m.match_score) : '—'}
                            </span>
                          </div>
                        </td>
                        <td>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', maxWidth: '140px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
                              <span style={{ color: 'var(--text-muted)' }}>Skills:</span>
                              <span style={{ fontWeight: '600' }}>{m.skills_score ? Math.round(m.skills_score) : 0}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
                              <span style={{ color: 'var(--text-muted)' }}>Exp:</span>
                              <span style={{ fontWeight: '600' }}>{m.experience_score ? Math.round(m.experience_score) : 0}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
                              <span style={{ color: 'var(--text-muted)' }}>Notice:</span>
                              <span style={{ fontWeight: '600' }}>{m.notice_period_score ? Math.round(m.notice_period_score) : 0}</span>
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
                              <span style={{ color: 'var(--text-muted)' }}>Loc:</span>
                              <span style={{ fontWeight: '600' }}>{m.location_score ? Math.round(m.location_score) : 0}</span>
                            </div>
                          </div>
                        </td>
                        <td style={{ maxWidth: '300px', fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.4' }}>
                          {m.explanation || '—'}
                        </td>
                        <td>
                          <select
                            className="select"
                            style={{ 
                              padding: '6px 10px', 
                              fontSize: '13px', 
                              borderRadius: 'var(--radius-sm)', 
                              width: 'auto',
                              fontWeight: '600',
                              backgroundColor: 'rgba(255,255,255,0.03)'
                            }}
                            value={m.status}
                            onChange={(e) => handleUpdateStatus(m.mapping_id, e.target.value)}
                          >
                            <option value="new">New</option>
                            <option value="shortlisted">Shortlisted</option>
                            <option value="screening_sent">Screening Sent</option>
                            <option value="screening_replied">Screening Replied</option>
                            <option value="recruiter_approved">Recruiter Approved</option>
                            <option value="recruiter_rejected">Recruiter Rejected</option>
                            <option value="interview_scheduled">Interview Scheduled</option>
                            <option value="client_submitted">Client Submitted</option>
                            <option value="rejected_by_client">Rejected by Client</option>
                            <option value="offer">Offer</option>
                            <option value="closed">Closed</option>
                          </select>
                        </td>
                        <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                          <div style={{ display: 'inline-flex', gap: '8px', alignItems: 'center', justifyContent: 'flex-end' }}>
                            <button 
                              className="btn btn-secondary btn-sm"
                              style={{ whiteSpace: 'nowrap' }}
                              title={`Re-run matching for ${m.full_name} alone`}
                              disabled={runningMatch}
                              onClick={() => handleRunMatchingForSelection([m.candidate_code], selectedJdId, true)}
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>
                              Re-score
                            </button>
                            <button 
                              className="btn btn-secondary btn-sm"
                              style={{ whiteSpace: 'nowrap' }}
                              disabled={m.status !== 'shortlisted' && m.status !== 'recruiter_approved'}
                              onClick={() => handleSendScreening(m.mapping_id, m.full_name)}
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg>
                              Email Screening
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* Candidate Selection Modal */}
      {showCandidatePicker && (
        <div className="modal-overlay" onClick={() => setShowCandidatePicker(false)}>
          <div className="modal-content" style={{ width: '720px' }} onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <div>
                <h2 className="card-title">Select Candidate CV(s) to Match</h2>
                <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
                  Choose which candidate profiles to score against a specific Job Description
                </p>
              </div>
              <button className="close-btn" onClick={() => setShowCandidatePicker(false)}>×</button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div className="form-group">
                <label>Target Job Specification *</label>
                <select 
                  className="select"
                  value={pickerJdId}
                  onChange={(e) => {
                    const newId = e.target.value;
                    setPickerJdId(newId);
                    fetchCandidatePool(newId);
                  }}
                  disabled={runningMatch}
                >
                  {jds.map((j) => (
                    <option key={j.jd_id} value={j.jd_id}>
                      {j.jd_code} - {j.role_title} ({j.client_name || 'Client'})
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="Filter CVs by candidate name, code, or skill..."
                  style={{ flex: 1, minWidth: '220px' }}
                  value={candidateSearchTerm}
                  onChange={(e) => setCandidateSearchTerm(e.target.value)}
                />

                <div style={{ display: 'flex', gap: '8px' }}>
                  <button 
                    type="button" 
                    className="btn btn-secondary btn-sm"
                    onClick={() => setSelectedCandidateCodes(filteredCandidates.map(c => c.candidate_code))}
                  >
                    Select All ({filteredCandidates.length})
                  </button>
                  <button 
                    type="button" 
                    className="btn btn-secondary btn-sm"
                    onClick={() => setSelectedCandidateCodes([])}
                  >
                    Deselect All
                  </button>
                </div>
              </div>

              <div style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
                <span>Showing {filteredCandidates.length} candidate CV(s) for this JD</span>
                <span style={{ color: 'var(--color-primary)', fontWeight: '600' }}>
                  {selectedCandidateCodes.length} of {filteredCandidates.length} selected
                </span>
              </div>

              <div className="candidate-picker-list">
                {loadingCandidates ? (
                  <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    <span className="spinner"></span> Loading candidate CVs for this JD...
                  </div>
                ) : allCandidates.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '40px 20px', color: 'var(--text-muted)' }}>
                    <div style={{ fontSize: '32px', marginBottom: '8px' }}>📄</div>
                    <p style={{ fontWeight: '600', color: 'var(--text-main)', fontSize: '14px' }}>No candidate CVs uploaded for this Job Description yet.</p>
                    <p style={{ fontSize: '12px', marginTop: '6px' }}>Click "+ Upload Candidate CV" to upload resumes associated with this role.</p>
                  </div>
                ) : filteredCandidates.length === 0 ? (
                  <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)' }}>
                    No candidate CVs matching "{candidateSearchTerm}".
                  </div>
                ) : (
                  filteredCandidates.map((c) => {
                    const isSelected = selectedCandidateCodes.includes(c.candidate_code);
                    return (
                      <div 
                        key={c.candidate_id} 
                        className={`candidate-picker-item ${isSelected ? 'selected' : ''}`}
                        onClick={() => {
                          setSelectedCandidateCodes(prev => 
                            isSelected ? prev.filter(code => code !== c.candidate_code) : [...prev, c.candidate_code]
                          );
                        }}
                      >
                        <input 
                          type="checkbox" 
                          className="candidate-picker-checkbox"
                          checked={isSelected}
                          onChange={() => {}}
                        />
                        <div className="candidate-picker-info">
                          <div className="candidate-picker-header">
                            <span className="candidate-picker-name">{c.full_name}</span>
                            <span className="candidate-picker-code">{c.candidate_code}</span>
                          </div>
                          <div className="candidate-picker-meta">
                            <span>Exp: {c.total_experience !== null ? `${c.total_experience} Yrs` : 'Not stated'}</span>
                            <span>•</span>
                            <span>{c.current_location || 'Location not specified'}</span>
                          </div>
                          {c.skills && c.skills.length > 0 && (
                            <div className="tags-list" style={{ marginTop: '4px' }}>
                              {c.skills.slice(0, 5).map((s, idx) => (
                                <span key={idx} className="tag" style={{ fontSize: '11px', padding: '1px 6px' }}>{s}</span>
                              ))}
                              {c.skills.length > 5 && (
                                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>+{c.skills.length - 5} more</span>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '12px' }}>
                <button 
                  type="button" 
                  className="btn btn-primary" 
                  style={{ flex: 1 }}
                  disabled={selectedCandidateCodes.length === 0 || runningMatch}
                  onClick={() => handleRunMatchingForSelection(selectedCandidateCodes, pickerJdId, false)}
                >
                  {runningMatch ? (
                    <><span className="spinner"></span> Running Matcher...</>
                  ) : (
                    `🚀 Run Match for ${selectedCandidateCodes.length} Selected CV(s)`
                  )}
                </button>
                <button 
                  type="button" 
                  className="btn btn-secondary" 
                  onClick={() => setShowCandidatePicker(false)}
                  disabled={runningMatch}
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Upload Candidate CV Drawer */}
      {showUploadDrawer && (
        <div className="modal-overlay" onClick={() => setShowUploadDrawer(false)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 className="card-title">Upload Candidate CV</h2>
              <button className="close-btn" onClick={() => setShowUploadDrawer(false)}>×</button>
            </div>

            <form onSubmit={handleUploadCv} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              <div className="form-group">
                <label>Job Specification context</label>
                <input 
                  type="text" 
                  className="input-text" 
                  style={{ opacity: 0.7 }}
                  value={activeJd ? `${activeJd.jd_code} - ${activeJd.role_title}` : 'None'} 
                  disabled 
                />
              </div>

              <div className="form-group">
                <label>Resume File (PDF / DOCX) *</label>
                <div 
                  className="file-upload-container"
                  onClick={() => document.getElementById('cv-file-input').click()}
                >
                  <input 
                    type="file" 
                    id="cv-file-input" 
                    style={{ display: 'none' }} 
                    accept=".pdf,.docx,.doc"
                    onChange={(e) => {
                      if (e.target.files && e.target.files.length > 0) {
                        setUploadFile(e.target.files[0]);
                      }
                    }}
                    disabled={isUploading}
                  />
                  <div className="file-upload-icon">📄</div>
                  <div className="file-upload-text">
                    {uploadFile ? (
                      <strong>Selected: {uploadFile.name}</strong>
                    ) : (
                      <span>Click to upload or <span>browse files</span></span>
                    )}
                  </div>
                  <div className="file-upload-subtext">PDF, DOCX formats supported (Max 10MB)</div>
                </div>
              </div>

              <div className="form-group">
                <label>Candidate Ingestion Source *</label>
                <select 
                  className="select" 
                  value={source} 
                  onChange={(e) => setSource(e.target.value)}
                  disabled={isUploading}
                >
                  <option value="manual_upload">Manual Upload</option>
                  <option value="linkedin_apply">LinkedIn Apply</option>
                  <option value="linkedin_dm">LinkedIn DM</option>
                  <option value="email">Email Submission</option>
                  <option value="naukri">Naukri portal</option>
                  <option value="referral">Internal Referral</option>
                </select>
              </div>

              <div className="form-group">
                <label>Source Details (Optional)</label>
                <input 
                  type="text" 
                  className="input-text" 
                  placeholder="e.g. LinkedIn JD-2026-0001 post response"
                  value={sourceDetail}
                  onChange={(e) => setSourceDetail(e.target.value)}
                  disabled={isUploading}
                />
              </div>

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button type="submit" className="btn btn-primary" style={{ flex: 1 }} disabled={isUploading || !uploadFile}>
                  {isUploading ? <span className="spinner"></span> : 'Upload & Match Candidate'}
                </button>
                <button type="button" className="btn btn-secondary" onClick={() => setShowUploadDrawer(false)} disabled={isUploading}>
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
