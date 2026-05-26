import { useEffect, useState } from 'react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import api from '../api'
import type { AlertStats } from '../api'

const PIE_COLORS: Record<string, string> = { HIGH: '#dc2626', MEDIUM: '#f59e0b', LOW: '#0f5a3a' }

export default function ManagerDashboard() {
  const [stats, setStats] = useState<AlertStats | null>(null)
  const [downloading, setDownloading] = useState<string | null>(null)

  useEffect(() => {
    api.get<AlertStats>('/alerts/stats').then(r => setStats(r.data)).catch(() => {})
  }, [])

  async function download(type: 'daily' | 'weekly') {
    setDownloading(type)
    try {
      const res = await api.get(`/reports/${type}`, { responseType: 'blob' })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url; a.download = `atm_sentinel_${type}_report.pdf`; a.click()
      URL.revokeObjectURL(url)
    } finally { setDownloading(null) }
  }

  const pieData = stats
    ? [{ name: 'HIGH', value: stats.high }, { name: 'MEDIUM', value: stats.medium }, { name: 'LOW', value: stats.low }].filter(d => d.value > 0)
    : []

  const cameraData = stats ? Object.entries(stats.by_camera).map(([cam, count]) => ({ cam, count })) : []

  const kpis = stats ? [
    { label: 'Total Alerts',    value: stats.total,          color: '#1f2937' },
    { label: 'HIGH',            value: stats.high,           color: '#dc2626' },
    { label: 'MEDIUM',          value: stats.medium,         color: '#f59e0b' },
    { label: 'LOW',             value: stats.low,            color: '#0f5a3a' },
    { label: 'Today',           value: stats.today,          color: '#1f2937' },
  ] : []

  return (
    <div className="security-page" style={{ padding: 32, maxWidth: 1200, background: '#f0fdf4', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1f2937', margin: 0 }}>Reports</h1>
          <p style={{ color: '#6b7280', margin: '6px 0 0', fontSize: 14 }}>Summary statistics and PDF exports</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          {(['daily', 'weekly'] as const).map(type => (
            <button
              key={type}
              onClick={() => download(type)}
              disabled={downloading === type}
              style={{ padding: '9px 18px', background: downloading === type ? '#f0f1f3' : '#f9fafb', border: '1px solid #f0f1f3', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', color: '#374151', transition: 'all 0.15s' }}
              onMouseEnter={e => !downloading && (e.currentTarget.style.borderColor = '#0f5a3a')}
              onMouseLeave={e => !downloading && (e.currentTarget.style.borderColor = '#f0f1f3')}
            >
              {downloading === type ? 'Generating…' : `↓ ${type.charAt(0).toUpperCase() + type.slice(1)} PDF`}
            </button>
          ))}
        </div>
      </div>

      {/* KPIs */}
      {stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 14, marginBottom: 28 }}>
          {kpis.map(k => (
            <div key={k.label} className="metric-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, padding: '18px 20px', boxShadow: '0 1px 2px rgba(0,0,0,0.05)', transition: 'all 0.15s' }} onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)')} onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)')}>
              <div className="metric-value" style={{ fontSize: 26, fontWeight: 700, color: k.color }}>{k.value}</div>
              <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4, fontWeight: 500 }}>{k.label}</div>
            </div>
          ))}
        </div>
      )}

      {/* Charts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        <div className="surface-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, padding: 24, boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: '#1f2937', margin: '0 0 20px' }}>Alert Level Distribution</h2>
          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80}
                  label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
                  labelLine={true}>
                  {pieData.map(e => <Cell key={e.name} fill={PIE_COLORS[e.name] ?? '#9ca3af'} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#f9fafb', border: '1px solid #f0f1f3', borderRadius: 8, fontSize: 12 }} />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>No data yet</div>
          )}
        </div>

        <div className="surface-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, padding: 24, boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, color: '#1f2937', margin: '0 0 20px' }}>Alerts by Camera</h2>
          {cameraData.length > 0 ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={cameraData} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
                <XAxis dataKey="cam" tick={{ fill: '#6b7280', fontSize: 12 }} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 12 }} />
                <Tooltip contentStyle={{ background: '#f9fafb', border: '1px solid #f0f1f3', borderRadius: 8, fontSize: 12 }} />
                <Bar dataKey="count" fill="#0f5a3a" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div style={{ height: 220, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca3af', fontSize: 13 }}>No data yet</div>
          )}
        </div>
      </div>
    </div>
  )
}
