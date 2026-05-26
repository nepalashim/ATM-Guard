import { useEffect, useState, type ReactNode } from 'react'
import api from '../api'
import type { Alert } from '../api'

const LEVELS = ['ALL', 'HIGH', 'MEDIUM', 'LOW']

const LEVEL_STYLE: Record<string, { bg: string; color: string; border: string }> = {
  HIGH:   { bg: '#fee2e2', color: '#dc2626', border: '#fecaca' },
  MEDIUM: { bg: '#fef3c7', color: '#92400e', border: '#fde68a' },
  LOW:    { bg: '#d1fae5', color: '#0f5a3a', border: '#6ee7b7' },
  NONE:   { bg: '#f5f5f5', color: '#6b7280', border: '#d1d5db' },
}

function getAlertDescription(alert: Alert): { label: string; color: string } {
  if (alert.alert_type === 'TOOL_DETECTED' && alert.object_detected) {
    const conf = alert.confidence ? ` (${(alert.confidence * 100).toFixed(1)}%)` : ''
    const name = alert.object_detected.replace(/_/g, ' ')
    return { label: `${name.charAt(0).toUpperCase() + name.slice(1)}${conf}`, color: '#dc2626' }
  }
  if (alert.alert_type === 'LOITERING') {
    const duration = Math.round(alert.loiter_sec || 0)
    const tid = alert.track_id != null ? ` · ID #${alert.track_id}` : ''
    return { label: `Loitering ${duration}s${tid}`, color: '#0f5a3a' }
  }
  if (alert.top_detection) {
    try {
      const obj = JSON.parse(alert.top_detection)
      if (obj.class_name) return { label: obj.class_name.charAt(0).toUpperCase() + obj.class_name.slice(1), color: '#374151' }
    } catch {}
    return { label: alert.top_detection, color: '#374151' }
  }
  return { label: '—', color: '#9ca3af' }
}

function BtnAction({ onClick, color, children }: { onClick: () => void; color: string; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      style={{ padding: '8px 16px', background: color, color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s' }}
      onMouseEnter={e => (e.currentTarget.style.opacity = '0.9')}
      onMouseLeave={e => (e.currentTarget.style.opacity = '1')}
    >
      {children}
    </button>
  )
}

export default function AlertHistory() {
  const role = localStorage.getItem('role') ?? 'supervisor'
  const isManager = role === 'manager'

  const [alerts, setAlerts]         = useState<Alert[]>([])
  const [level, setLevel]           = useState('ALL')
  const [camId, setCamId]           = useState('')
  const [loading, setLoading]       = useState(false)
  const [selected, setSelected]     = useState<Alert | null>(null)
  const [comment, setComment]           = useState('')
  const [mgrComment, setMgrComment]     = useState('')
  const [saving, setSaving]             = useState(false)
  const [savingMgr, setSavingMgr]       = useState(false)
  const [commentSaved, setCommentSaved] = useState(false)
  const [mgrSaved, setMgrSaved]         = useState(false)
  const [showVideo, setShowVideo]       = useState(false)

  async function load() {
    setLoading(true)
    const params: Record<string, string> = { limit: '300' }
    if (level !== 'ALL') params.level = level
    if (camId.trim()) params.cam_id = camId.trim()
    // Manager only sees escalated alerts
    if (isManager) params.escalated = 'true'
    try {
      const { data } = await api.get<Alert[]>('/alerts', { params })
      setAlerts(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [level])

  async function refreshSelected(id: number) {
    const { data } = await api.get<Alert>(`/alerts/${id}`)
    setSelected(data)
    setAlerts(prev => prev.map(a => a.id === id ? data : a))
  }

  async function openAlert(a: Alert) {
    setSelected(a)
    setComment(a.comment ?? '')
    setMgrComment(a.manager_comment ?? '')
    setCommentSaved(!!a.comment)
    setMgrSaved(!!a.manager_comment)
    setShowVideo(false)
    try {
      const { data } = await api.get<Alert>(`/alerts/${a.id}`)
      setSelected(data)
      setComment(data.comment ?? '')
      setMgrComment(data.manager_comment ?? '')
      setCommentSaved(!!data.comment)
      setMgrSaved(!!data.manager_comment)
      setAlerts(prev => prev.map(item => item.id === data.id ? data : item))
    } catch {}
  }

  async function ack() {
    if (!selected) return
    await api.post(`/alerts/${selected.id}/acknowledge`)
    refreshSelected(selected.id)
  }

  async function saveComment() {
    if (!selected) return
    setSaving(true)
    try {
      await api.post(`/alerts/${selected.id}/comment`, { text: comment })
      setCommentSaved(true)
      refreshSelected(selected.id)
    } finally { setSaving(false) }
  }

  async function saveMgrComment() {
    if (!selected) return
    setSavingMgr(true)
    try {
      await api.post(`/alerts/${selected.id}/manager-comment`, { text: mgrComment })
      setMgrSaved(true)
      refreshSelected(selected.id)
    } finally { setSavingMgr(false) }
  }

  async function markTrue()  { if (selected) { await api.post(`/alerts/${selected.id}/mark-true`);  refreshSelected(selected.id) } }
  async function markFalse() { if (selected) { await api.post(`/alerts/${selected.id}/mark-false`); refreshSelected(selected.id) } }
  async function escalate()  { if (selected) { await api.post(`/alerts/${selected.id}/escalate`);   refreshSelected(selected.id) } }

  async function triggerSOS() {
    if (!selected) return
    if (!window.confirm('Trigger SOS for this alert? An emergency email will be sent.')) return
    await api.post(`/alerts/${selected.id}/sos`)
    window.alert('SOS triggered.')
  }

  return (
    <div className="security-page" style={{ padding: 32, maxWidth: 1400, background: '#f0fdf4', minHeight: '100vh' }}>

      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1f2937', margin: 0 }}>Alert History</h1>
        <p style={{ color: '#6b7280', margin: '6px 0 0', fontSize: 14 }}>
          {alerts.length} records — {isManager ? 'escalated alerts only' : 'click a row to review'}
        </p>
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 20, alignItems: 'center' }}>
        <div style={{ display: 'flex', background: '#f9fafb', border: '1px solid #f0f1f3', borderRadius: 8, padding: 4, gap: 2 }}>
          {LEVELS.map(l => (
            <button key={l} onClick={() => setLevel(l)}
              style={{ padding: '5px 14px', borderRadius: 6, fontSize: 12, fontWeight: 500, border: 'none', cursor: 'pointer',
                background: level === l ? '#0f5a3a' : 'transparent', color: level === l ? '#ffffff' : '#6b7280', transition: 'all 0.15s' }}
              onMouseEnter={e => !((level === l)) && (e.currentTarget.style.background = '#f3f4f6')}
              onMouseLeave={e => !((level === l)) && (e.currentTarget.style.background = 'transparent')}>
              {l}
            </button>
          ))}
        </div>
        <input value={camId} onChange={e => setCamId(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()}
          placeholder="Camera ID (Enter)"
          style={{ padding: '7px 14px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 13, color: '#1f2937', background: '#f9fafb', outline: 'none', width: 180, transition: 'all 0.15s' }}
          onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
          onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')} />
        <button onClick={load}
          style={{ padding: '7px 16px', background: '#0f5a3a', color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s' }}
          onMouseEnter={e => (e.currentTarget.style.background = '#0d4a2f')}
          onMouseLeave={e => (e.currentTarget.style.background = '#0f5a3a')}>
          Refresh
        </button>
      </div>

      {/* Table */}
      <div className="surface-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #f0f1f3', background: '#ffffff' }}>
              {['Time', 'Camera', 'Level', 'Detection', 'Loiter', 'Status', ''].map(h => (
                <th key={h} style={{ padding: '11px 16px', textAlign: 'left', fontSize: 12, fontWeight: 600, color: '#6b7280', letterSpacing: 0.3 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading && <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>Loading…</td></tr>}
            {!loading && alerts.length === 0 && (
              <tr><td colSpan={7} style={{ textAlign: 'center', padding: 40, color: '#9ca3af' }}>
                {isManager ? 'No escalated alerts yet' : 'No alerts found'}
              </td></tr>
            )}
            {!loading && alerts.map((a, i) => {
              const s = LEVEL_STYLE[a.level] ?? LEVEL_STYLE.NONE
              const det = getAlertDescription(a)
              return (
                <tr key={a.id} onClick={() => openAlert(a)}
                  style={{ borderBottom: '1px solid #f0f1f3', background: i % 2 === 0 ? '#dff7f4' : '#e8faf7', cursor: 'pointer', transition: 'all 0.15s' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#d0eff0')}
                  onMouseLeave={e => (e.currentTarget.style.background = i % 2 === 0 ? '#dff7f4' : '#e8faf7')}>
                  <td style={{ padding: '11px 16px', color: '#6b7280', whiteSpace: 'nowrap' }}>{new Date(a.timestamp).toLocaleString()}</td>
                  <td data-font="mono" style={{ padding: '11px 16px', fontSize: 12, color: '#1f2937', fontWeight: 600 }}>{a.cam_id}</td>
                  <td style={{ padding: '11px 16px' }}>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '3px 8px', borderRadius: 4, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>{a.level}</span>
                  </td>
                  <td style={{ padding: '11px 16px', color: det.color, fontWeight: 500 }}>{det.label}</td>
                  <td style={{ padding: '11px 16px', color: '#374151' }}>{a.loiter_sec > 0 ? `${a.loiter_sec}s` : '—'}</td>
                  <td style={{ padding: '11px 16px' }}>
                    {a.is_false_alert
                      ? <span style={{ fontSize: 11, padding: '2px 8px', background: '#f9fafb', color: '#6b7280', borderRadius: 4, border: '1px solid #f0f1f3' }}>False Alert</span>
                      : a.acknowledged
                        ? <span style={{ fontSize: 11, padding: '2px 8px', background: '#f0fdf4', color: '#15803d', borderRadius: 4, border: '1px solid #bbf7d0' }}>Acknowledged</span>
                        : <span style={{ fontSize: 11, padding: '2px 8px', background: '#fef2f2', color: '#dc2626', borderRadius: 4, border: '1px solid #fecaca' }}>Open</span>
                    }
                  </td>
                  <td style={{ padding: '11px 16px', color: '#9ca3af', fontSize: 12 }}>View →</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {/* Modal */}
      {selected && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
          onClick={e => { if (e.target === e.currentTarget) setSelected(null) }}>
          <div className="surface-card" style={{ background: '#dff7f4', borderRadius: 16, padding: 32, width: 820, maxWidth: '95vw', maxHeight: '90vh', overflow: 'auto', boxShadow: '0 24px 64px rgba(0,0,0,0.15)' }}>

            {/* Header */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
              <div>
                <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: '#1f2937' }}>Alert #{selected.id}</h2>
                <p style={{ margin: '6px 0 0', color: '#6b7280', fontSize: 13 }}>{selected.cam_id} · {new Date(selected.timestamp).toLocaleString()}</p>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                {(() => { const s = LEVEL_STYLE[selected.level] ?? LEVEL_STYLE.NONE; return (
                  <span style={{ fontSize: 12, fontWeight: 700, padding: '4px 12px', borderRadius: 6, background: s.bg, color: s.color, border: `1px solid ${s.border}` }}>{selected.level}</span>
                )})()}
                <button onClick={() => setSelected(null)} style={{ background: 'none', border: 'none', fontSize: 22, cursor: 'pointer', color: '#6b7280', lineHeight: 1, padding: 0 }}>×</button>
              </div>
            </div>

            {/* Snapshot */}
            {selected.frame_path ? (
              <div style={{ marginBottom: 16 }}>
                <p style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: 0.5 }}>Snapshot</p>
                <img src={`/${selected.frame_path}`} alt="Alert snapshot"
                  style={{ width: '100%', borderRadius: 8, border: '1px solid #f0f1f3', display: 'block' }} />
              </div>
            ) : (
              <div style={{ background: '#dff7f4', borderRadius: 8, padding: 32, textAlign: 'center', color: '#9ca3af', fontSize: 13, marginBottom: 16, border: '1px dashed #f0f1f3' }}>
                No snapshot captured for this alert
              </div>
            )}

            {/* Video clip button */}
            {selected.video_path && (
              <div style={{ marginBottom: 24 }}>
                {!showVideo ? (
                  <button onClick={() => setShowVideo(true)}
                    style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '9px 18px', background: '#0f172a', color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: 'pointer', transition: 'all 0.15s' }}
                    onMouseEnter={e => (e.currentTarget.style.opacity = '0.9')}
                    onMouseLeave={e => (e.currentTarget.style.opacity = '1')}>
                    <span style={{ fontSize: 16 }}>▶</span> Play 5s Video Clip
                  </button>
                ) : (
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                      <p style={{ fontSize: 11, fontWeight: 600, color: '#6b7280', margin: 0, textTransform: 'uppercase', letterSpacing: 0.5 }}>Video Clip (5s)</p>
                      <button onClick={() => setShowVideo(false)}
                        style={{ background: 'none', border: 'none', fontSize: 12, color: '#9ca3af', cursor: 'pointer' }}>Hide</button>
                    </div>
                    <video src={`/${selected.video_path}`} controls autoPlay muted
                      style={{ width: '100%', borderRadius: 8, border: '1px solid #e5e7eb', display: 'block' }} />
                  </div>
                )}
              </div>
            )}

            {/* Alert details */}
            <div style={{ display: 'flex', gap: 24, marginBottom: 24, background: '#f9fafb', borderRadius: 8, padding: '12px 16px', flexWrap: 'wrap' }}>
              {selected.alert_type === 'TOOL_DETECTED' && (
                <>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>Tool: <strong style={{ color: '#1f2937' }}>{selected.object_detected ?? '—'}</strong></span>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>Verdict: <strong style={{ color: selected.is_false_alert ? '#6b7280' : '#dc2626' }}>{selected.is_false_alert ? 'False Alert' : 'True Threat'}</strong></span>
                </>
              )}
              {selected.alert_type === 'LOITERING' && (
                <>
                  <span style={{ fontSize: 13, color: '#6b7280' }}>Duration: <strong style={{ color: '#1f2937' }}>{selected.loiter_sec}s</strong></span>
                  {selected.track_id != null && <span style={{ fontSize: 13, color: '#6b7280' }}>Track ID: <strong style={{ color: '#1f2937' }}>#{selected.track_id}</strong></span>}
                  <span style={{ fontSize: 13, color: '#6b7280' }}>Verdict: <strong style={{ color: selected.is_false_alert ? '#6b7280' : '#0f5a3a' }}>{selected.is_false_alert ? 'False Alert' : 'Open'}</strong></span>
                </>
              )}
              <span style={{ fontSize: 13, color: '#6b7280' }}>Escalated: <strong style={{ color: '#1f2937' }}>{selected.escalated ? 'Yes' : 'No'}</strong></span>
            </div>

            {/* ── SUPERVISOR VIEW ── */}
            {!isManager && (
              <>
                <div style={{ marginBottom: 24 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Investigation Notes</label>
                    {commentSaved && (
                      <button onClick={() => setCommentSaved(false)}
                        style={{ fontSize: 12, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
                        Edit
                      </button>
                    )}
                  </div>
                  {commentSaved ? (
                    <div style={{ padding: '10px 12px', background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 8, fontSize: 13, color: '#1f2937', minHeight: 48 }}>
                      {comment || <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>No notes added</span>}
                    </div>
                  ) : (
                    <>
                      <textarea value={comment} onChange={e => { setComment(e.target.value); setCommentSaved(false) }} rows={3}
                        placeholder="Add investigation notes or context…"
                        style={{ width: '100%', padding: '10px 12px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 13, color: '#1f2937', background: '#f9fafb', resize: 'vertical', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box', transition: 'all 0.15s' }}
                        onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                        onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')} />
                      <button onClick={saveComment} disabled={saving}
                        style={{ marginTop: 8, padding: '7px 16px', background: saving ? '#b0e0c0' : '#0f5a3a', color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: saving ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}
                        onMouseEnter={e => !saving && (e.currentTarget.style.background = '#0d4a2f')}
                        onMouseLeave={e => !saving && (e.currentTarget.style.background = '#0f5a3a')}>
                        {saving ? 'Saving…' : 'Save Comment'}
                      </button>
                    </>
                  )}
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, paddingTop: 20, borderTop: '1px solid #f3f4f6' }}>
                  {!selected.acknowledged && <BtnAction onClick={ack} color="#15803d">Acknowledge</BtnAction>}
                  <BtnAction onClick={markTrue} color="#374151">Mark True Threat</BtnAction>
                  <BtnAction onClick={markFalse} color="#6b7280">Mark False Alert</BtnAction>
                  {!selected.escalated
                    ? <BtnAction onClick={escalate} color="#f59e0b">Escalate to Manager</BtnAction>
                    : <span style={{ fontSize: 13, color: '#f59e0b', fontWeight: 500, padding: '8px 0' }}>Escalated to Manager</span>
                  }
                  {selected.level === 'HIGH' && <BtnAction onClick={triggerSOS} color="#dc2626">SOS</BtnAction>}
                </div>
              </>
            )}

            {/* ── MANAGER VIEW ── */}
            {isManager && (
              <>
                {/* Supervisor notes — read only */}
                <div style={{ marginBottom: 24, background: '#fef3c7', borderRadius: 8, padding: 16, border: '1px solid #fde68a' }}>
                  <p style={{ fontSize: 12, fontWeight: 600, color: '#92400e', margin: '0 0 8px', textTransform: 'uppercase', letterSpacing: 0.4 }}>Supervisor Notes</p>
                  <p style={{ fontSize: 13, color: '#78350f', margin: 0, fontStyle: selected.comment ? 'normal' : 'italic' }}>
                    {selected.comment || 'No notes left by supervisor'}
                  </p>
                </div>

                {/* Manager's own notes */}
                <div style={{ marginBottom: 24 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <label style={{ fontSize: 13, fontWeight: 600, color: '#374151' }}>Manager Notes</label>
                    {mgrSaved && (
                      <button onClick={() => setMgrSaved(false)}
                        style={{ fontSize: 12, color: '#6b7280', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}>
                        Edit
                      </button>
                    )}
                  </div>
                  {mgrSaved ? (
                    <div style={{ padding: '10px 12px', background: '#f5f5f5', border: '1px solid #d1d5db', borderRadius: 8, fontSize: 13, color: '#1f2937', minHeight: 48 }}>
                      {mgrComment || <span style={{ color: '#9ca3af', fontStyle: 'italic' }}>No notes added</span>}
                    </div>
                  ) : (
                    <>
                      <textarea value={mgrComment} onChange={e => { setMgrComment(e.target.value); setMgrSaved(false) }} rows={3}
                        placeholder="Add your review notes…"
                        style={{ width: '100%', padding: '10px 12px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 13, color: '#1f2937', background: '#f9fafb', resize: 'vertical', outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box', transition: 'all 0.15s' }}
                        onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                        onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')} />
                      <button onClick={saveMgrComment} disabled={savingMgr}
                        style={{ marginTop: 8, padding: '7px 16px', background: savingMgr ? '#b0e0c0' : '#0f5a3a', color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 500, cursor: savingMgr ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}
                        onMouseEnter={e => !savingMgr && (e.currentTarget.style.background = '#0d4a2f')}
                        onMouseLeave={e => !savingMgr && (e.currentTarget.style.background = '#0f5a3a')}>
                        {savingMgr ? 'Saving…' : 'Save Notes'}
                      </button>
                    </>
                  )}
                </div>

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, paddingTop: 20, borderTop: '1px solid #f3f4f6' }}>
                  {!selected.acknowledged && <BtnAction onClick={ack} color="#15803d">Acknowledge</BtnAction>}
                  {selected.level === 'HIGH' && <BtnAction onClick={triggerSOS} color="#dc2626">SOS</BtnAction>}
                </div>
              </>
            )}

          </div>
        </div>
      )}
    </div>
  )
}
