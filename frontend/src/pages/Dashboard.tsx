import { useEffect, useState, useRef } from 'react'
import api from '../api'
import type { Alert, Camera } from '../api'

const LEVEL_STYLE: Record<string, { bg: string; color: string; border: string }> = {
  HIGH:   { bg: '#fee2e2', color: '#dc2626', border: '#fecaca' },
  MEDIUM: { bg: '#fef3c7', color: '#92400e', border: '#fde68a' },
  LOW:    { bg: '#d1fae5', color: '#0f5a3a', border: '#6ee7b7' },
  NONE:   { bg: '#f5f5f5', color: '#6b7280', border: '#d1d5db' },
}

const LEVEL_BAR: Record<string, string> = {
  HIGH: '#dc2626', MEDIUM: '#f59e0b', LOW: '#0f5a3a', NONE: '#d1d5db',
}

function CameraFeed({ camera }: { camera: Camera }) {
  const [error, setError] = useState(false)
  const [streamUrl] = useState(`/api/cameras/${camera.cam_id}/stream`)

  return (
    <div className="surface-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', transition: 'all 0.25s ease' }}
      onMouseEnter={e => {
        e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)'
        e.currentTarget.style.borderColor = '#e5e7eb'
        e.currentTarget.style.background = '#cef1ef'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)'
        e.currentTarget.style.borderColor = '#f0f1f3'
        e.currentTarget.style.background = '#dff7f4'
      }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 20px', borderBottom: '1px solid #bfe8ba', background: '#def7da' }}>
        <div>
          <span className="feed-camera-title" style={{ fontWeight: 700, fontSize: 14, color: '#14351f' }}>{camera.name}</span>
        </div>
        <span className="feed-status-pill" style={{ fontSize: 12, padding: '4px 12px', background: '#dff7f4', color: '#0f5a3a', borderRadius: 6, fontWeight: 700, letterSpacing: 0.5 }}>● LIVE</span>
      </div>
      <div style={{ position: 'relative', width: '100%', paddingBottom: '56.25%', background: '#000', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        {error ? (
          <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#dc2626', fontSize: 14, background: '#fef2f2', padding: 20, textAlign: 'center' }}>
            <div>
              <div style={{ fontWeight: 700, marginBottom: 10, fontSize: 15 }}>⚠ Stream Error</div>
              <div style={{ fontSize: 13, color: '#991b1b', marginBottom: 10 }}>RTSP connection failed</div>
              <div data-font="mono" style={{ fontSize: 12, color: '#7f1d1d', wordBreak: 'break-all', marginBottom: 6 }}>{camera.url}</div>
              <div style={{ fontSize: 11, color: '#a16162', marginTop: 10 }}>Verify camera is online</div>
            </div>
          </div>
        ) : null}
        <img
          key={streamUrl}
          src={streamUrl}
          alt={`${camera.name} MJPEG Stream`}
          className="feed-camera-title"
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', objectFit: 'contain', display: error ? 'none' : 'block' }}
          onError={() => setError(true)}
        />
      </div>
    </div>
  )
}

function AlertRow({ alert, onAck }: { alert: Alert; onAck: (id: number) => void }) {
  const isManager = (localStorage.getItem('role') ?? 'supervisor') === 'manager'
  const s = LEVEL_STYLE[alert.level] ?? LEVEL_STYLE.NONE
  
  // Determine alert description based on type
  let alertDesc = ''
  if (alert.alert_type === 'TOOL_DETECTED') {
    const conf = alert.confidence ? (alert.confidence * 100).toFixed(1) : '?'
    alertDesc = `Tool Detected: ${alert.object_detected} (${conf}%)`
  } else if (alert.alert_type === 'LOITERING') {
    alertDesc = `Loitering: ${Math.round(alert.loiter_sec)}s`
  } else {
    // Legacy format
    alertDesc = `${alert.n_detections} detection${alert.n_detections !== 1 ? 's' : ''} · Loiter ${Math.round(alert.loiter_sec)}s`
  }
  
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '14px 20px', borderBottom: '1px solid #f0f1f3', background: '#ffffff', transition: 'all 0.2s ease' }}
      onMouseEnter={e => {
        e.currentTarget.style.background = '#fafbfc'
      }}
      onMouseLeave={e => {
        e.currentTarget.style.background = '#ffffff'
      }}>
      <div style={{ width: 4, height: 44, borderRadius: 2, background: LEVEL_BAR[alert.level], flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 700, padding: '3px 10px', borderRadius: 5, background: s.bg, color: s.color, border: `1.5px solid ${s.border}`, letterSpacing: 0.3 }}>
            {alert.level}
          </span>
          <span style={{ fontSize: 14, fontWeight: 600, color: '#0f172a' }}>{alert.cam_id}</span>
          <span style={{ fontSize: 13, color: '#6b7280', fontWeight: 500 }}>· {alertDesc}</span>
        </div>
        <div style={{ fontSize: 12, color: '#9ca3af', fontWeight: 400 }}>
          {new Date(alert.timestamp).toLocaleTimeString()}
          {alert.detection_source && ` · ${alert.detection_source}`}
        </div>
      </div>
      {alert.acknowledged ? (
        <span style={{ fontSize: 13, color: '#059669', fontWeight: 600, whiteSpace: 'nowrap' }}>✓ Acknowledged</span>
      ) : !isManager ? (
        <button
          onClick={() => onAck(alert.id)}
          style={{ fontSize: 13, padding: '7px 16px', background: '#ffffff', border: '1.5px solid #d1d5db', borderRadius: 7, cursor: 'pointer', color: '#374151', fontWeight: 600, transition: 'all 0.2s ease', whiteSpace: 'nowrap' }}
          onMouseEnter={e => { 
            e.currentTarget.style.borderColor = '#0f5a3a'
            e.currentTarget.style.color = '#0f5a3a'
            e.currentTarget.style.background = '#f0fdf4'
          }}
          onMouseLeave={e => { 
            e.currentTarget.style.borderColor = '#d1d5db'
            e.currentTarget.style.color = '#374151'
            e.currentTarget.style.background = '#ffffff'
          }}
        >
          Acknowledge
        </button>
      ) : null}
    </div>
  )
}

export default function Dashboard() {
  const role      = localStorage.getItem('role') ?? 'supervisor'
  const isManager = role === 'manager'

  const [alerts, setAlerts] = useState<Alert[]>([])
  const [cameras, setCameras] = useState<Camera[]>([])
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    const params: Record<string, string | number> = { limit: 30, ordering: '-timestamp' }
    if (isManager) params.escalated = 'true'

    api.get<Alert[]>('/alerts', { params }).then(r => setAlerts(r.data)).catch(() => {})
    api.get<Camera[]>('/cameras').then(r => setCameras(r.data.filter(c => c.is_active))).catch(() => {})

    const token = localStorage.getItem('token')
    let ws: WebSocket | null = null
    let cancelled = false
    let retryDelay = 2000

    function connect() {
      if (cancelled) return
      ws = new WebSocket(`ws://localhost:8000/ws/alerts?token=${token}`)
      wsRef.current = ws
      ws.onopen = () => { if (!cancelled) { setConnected(true); retryDelay = 2000 } }
      ws.onclose = () => { if (!cancelled) { setConnected(false); setTimeout(connect, retryDelay); retryDelay = Math.min(retryDelay * 2, 30000) } }
      ws.onerror = () => ws?.close()
      ws.onmessage = e => {
        try {
          const a: Alert = JSON.parse(e.data)
          // Manager only receives escalated alerts in their feed
          if (isManager && !a.escalated) return
          setAlerts(prev => [a, ...prev].slice(0, 100))
        } catch {}
      }
    }

    const t = setTimeout(connect, 500)
    return () => { cancelled = true; clearTimeout(t); ws?.close() }
  }, [])

  async function ack(id: number) {
    await api.post(`/alerts/${id}/acknowledge`)
    setAlerts(prev => prev.map(a => a.id === id ? { ...a, acknowledged: true } : a))
  }

  const highActive = alerts.filter(a => a.level === 'HIGH' && !a.acknowledged)
  const unacked    = alerts.filter(a => !a.acknowledged)

  // Supervisor stats: Total, HIGH Active, Unacknowledged, Cameras Online
  // Manager stats:    Total (escalated), HIGH Active (escalated), Cameras Online  — no Unacknowledged
  const stats = isManager
    ? [
        { label: 'Escalated Alerts', value: alerts.length,      color: '#1e293b' },
        { label: 'HIGH Active',       value: highActive.length,  color: '#dc2626' },
        { label: 'Cameras Online',    value: cameras.length,     color: '#2563eb' },
      ]
    : [
        { label: 'Total Alerts',      value: alerts.length,      color: '#1e293b' },
        { label: 'HIGH Active',       value: highActive.length,  color: '#dc2626' },
        { label: 'Unacknowledged',    value: unacked.length,     color: '#d97706' },
        { label: 'Cameras Online',    value: cameras.length,     color: '#2563eb' },
      ]

  const gridCols = isManager ? 'repeat(3, 1fr)' : 'repeat(4, 1fr)'

  return (
      <div className="security-page" style={{ padding: '40px 48px', maxWidth: 1400, background: '#f0fdf4', minHeight: '100vh' }}>
      {/* Header - Connection Status */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end', marginBottom: 36 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 18px', background: '#f9fafb', border: '1.5px solid #f0f1f3', borderRadius: 8, boxShadow: '0 2px 4px rgba(0,0,0,0.08)', transition: 'all 0.2s' }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', background: connected ? '#10b981' : '#ef4444', display: 'inline-block' }} />
          <span style={{ fontSize: 14, color: '#374151', fontWeight: 600 }}>{connected ? 'Connected' : 'Reconnecting…'}</span>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: gridCols, gap: 20, marginBottom: 36 }}>
        {stats.map(s => (
          <div key={s.label} className="metric-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, padding: '24px 28px', boxShadow: '0 1px 3px rgba(0,0,0,0.08)', transition: 'all 0.25s ease', cursor: 'default' }}
            onMouseEnter={e => {
              e.currentTarget.style.boxShadow = '0 4px 12px rgba(0,0,0,0.12)'
              e.currentTarget.style.transform = 'translateY(-2px)'
              e.currentTarget.style.background = '#d0eff0'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)'
              e.currentTarget.style.transform = 'translateY(0)'
              e.currentTarget.style.background = '#dff7f4'
            }}>
            <div className="metric-value" style={{ fontSize: 32, fontWeight: 800, color: s.color, lineHeight: 1 }}>{s.value}</div>
            <div style={{ fontSize: 13, color: '#6b7280', marginTop: 10, fontWeight: 500, letterSpacing: 0.3 }}>{s.label.toUpperCase()}</div>
          </div>
        ))}
      </div>

      {/* Camera feeds */}
      {cameras.length > 0 && (
        <div style={{ marginBottom: 36 }}>
          <h2 className="feed-section-title" style={{ fontSize: 18, fontWeight: 900, color: '#001f5b', margin: '0 0 18px', letterSpacing: 0, borderLeft: '4px solid #001f5b', paddingLeft: 10 }}>LIVE FEEDS</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 20 }}>
            {cameras.map(c => <CameraFeed key={c.id} camera={c} />)}
          </div>
        </div>
      )}

      {/* Alert feed */}
      <div>
        <h2 className="feed-section-title" style={{ fontSize: 18, fontWeight: 900, color: '#001f5b', margin: '0 0 18px', letterSpacing: 0, borderLeft: '4px solid #001f5b', paddingLeft: 10 }}>
          {isManager ? 'ESCALATED ALERTS' : 'RECENT ALERTS'}
        </h2>
        <div className="surface-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.08)' }}>
          {alerts.length === 0 ? (
            <div className="feed-empty-state" style={{ padding: '60px 32px', textAlign: 'center', color: '#9ca3af', fontSize: 15, fontWeight: 500 }}>
              <div style={{ fontSize: 13, marginBottom: 8 }}>✓</div>
              {isManager ? 'No escalated alerts' : 'System monitoring — no alerts yet'}
            </div>
          ) : (
            alerts.map(a => <AlertRow key={a.id} alert={a} onAck={isManager ? () => {} : ack} />)
          )}
        </div>
      </div>
    </div>
  )
}
