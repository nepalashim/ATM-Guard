import { useEffect, useState } from 'react'
import api from '../api'
import type { Camera } from '../api'

const EMPTY: Omit<Camera, 'id' | 'created_at'> = {
  cam_id: '', name: '', url: '', location: '',
  latitude: null, longitude: null, is_active: true,
}

export default function CameraManager() {
  const [cameras, setCameras] = useState<Camera[]>([])
  const [form, setForm] = useState({ ...EMPTY })
  const [editId, setEditId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')

  async function load() {
    const { data } = await api.get<Camera[]>('/cameras')
    setCameras(data)
  }

  useEffect(() => { load() }, [])

  function openAdd() { setForm({ ...EMPTY }); setEditId(null); setShowForm(true); setError('') }
  function openEdit(c: Camera) {
    setForm({ cam_id: c.cam_id, name: c.name, url: c.url, location: c.location, latitude: c.latitude, longitude: c.longitude, is_active: c.is_active })
    setEditId(c.id); setShowForm(true); setError('')
  }

  async function save() {
    setError('')
    try {
      if (editId !== null) await api.put(`/cameras/${editId}`, form)
      else await api.post('/cameras', form)
      setShowForm(false); load()
    } catch (e: any) { setError(e.response?.data?.detail ?? 'Save failed') }
  }

  async function remove(id: number) {
    if (!confirm('Delete this camera?')) return
    await api.delete(`/cameras/${id}`); load()
  }

  const inputStyle = { width: '100%', padding: '9px 12px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 13, color: '#1f2937', background: '#f9fafb', outline: 'none', transition: 'all 0.15s' }

  return (
    <div className="security-page" style={{ padding: 32, maxWidth: 1200, background: '#f0fdf4', minHeight: '100vh' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#1f2937', margin: 0 }}>Camera Manager</h1>
          <p style={{ color: '#6b7280', margin: '6px 0 0', fontSize: 14 }}>{cameras.length} cameras configured</p>
        </div>
        <button
          onClick={openAdd}
          style={{ padding: '9px 20px', background: '#0f5a3a', color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s' }}
          onMouseEnter={e => (e.currentTarget.style.background = '#0d4a2f')}
          onMouseLeave={e => (e.currentTarget.style.background = '#0f5a3a')}
        >
          + Add Camera
        </button>
      </div>

      {/* Modal */}
      {showForm && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(15, 23, 42, 0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 50 }}>
          <div style={{ background: '#f9fafb', borderRadius: 12, padding: 28, width: '100%', maxWidth: 440, boxShadow: '0 20px 25px rgba(0,0,0,0.15)' }}>
            <h2 style={{ fontSize: 17, fontWeight: 700, color: '#1f2937', margin: '0 0 20px' }}>
              {editId ? 'Edit Camera' : 'Add Camera'}
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {[
                { key: 'cam_id', label: 'Camera ID', placeholder: 'camA' },
                { key: 'name',   label: 'Name',      placeholder: 'Main Entrance ATM' },
                { key: 'url',    label: 'Stream URL', placeholder: 'rtsp://...' },
                { key: 'location', label: 'Location', placeholder: 'Branch 1, Floor 2' },
              ].map(f => (
                <div key={f.key}>
                  <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 5 }}>{f.label}</label>
                  <input
                    value={(form as any)[f.key] ?? ''}
                    onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                    placeholder={f.placeholder}
                    style={inputStyle}
                    onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                    onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')}
                  />
                </div>
              ))}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                {(['latitude', 'longitude'] as const).map(k => (
                  <div key={k}>
                    <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: '#374151', marginBottom: 5, textTransform: 'capitalize' }}>{k}</label>
                    <input
                      type="number" step="any"
                      value={form[k] ?? ''}
                      onChange={e => setForm(p => ({ ...p, [k]: e.target.value ? parseFloat(e.target.value) : null }))}
                      style={inputStyle}
                      onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                      onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')}
                    />
                  </div>
                ))}
              </div>
              <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#374151', cursor: 'pointer' }}>
                <input type="checkbox" checked={form.is_active} onChange={e => setForm(p => ({ ...p, is_active: e.target.checked }))} style={{ accentColor: '#0f5a3a' }} />
                Active
              </label>
              {error && <p style={{ color: '#dc2626', fontSize: 13, margin: 0, fontWeight: 500 }}>{error}</p>}
              <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 8 }}>
                <button onClick={() => setShowForm(false)} style={{ padding: '8px 18px', background: '#f9fafb', border: '1px solid #f0f1f3', borderRadius: 8, fontSize: 13, cursor: 'pointer', color: '#374151', fontWeight: 500, transition: 'all 0.15s' }} onMouseEnter={e => (e.currentTarget.style.background = '#f0f1f3')} onMouseLeave={e => (e.currentTarget.style.background = '#f9fafb')}>Cancel</button>
                <button onClick={save} style={{ padding: '8px 18px', background: '#0f5a3a', border: 'none', borderRadius: 8, fontSize: 13, fontWeight: 600, cursor: 'pointer', color: '#ffffff', transition: 'all 0.15s' }} onMouseEnter={e => (e.currentTarget.style.background = '#0d4a2f')} onMouseLeave={e => (e.currentTarget.style.background = '#0f5a3a')}>Save</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Camera grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 16 }}>
        {cameras.map(c => (
          <div key={c.id} className="surface-card" style={{ background: '#dff7f4', border: '1px solid #f0f1f3', borderRadius: 12, padding: 20, boxShadow: '0 1px 2px rgba(0,0,0,0.05)', transition: 'all 0.15s' }} onMouseEnter={e => (e.currentTarget.style.boxShadow = '0 4px 6px rgba(0,0,0,0.1)')} onMouseLeave={e => (e.currentTarget.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)')}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12 }}>
              <div>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#1f2937' }}>{c.name}</div>
                <div data-font="mono" style={{ fontSize: 12, color: '#6b7280', marginTop: 2 }}>{c.cam_id}</div>
              </div>
              <span style={{ fontSize: 11, padding: '3px 10px', borderRadius: 20, fontWeight: 500, background: c.is_active ? '#dcfce7' : '#f3f4f6', color: c.is_active ? '#15803d' : '#6b7280' }}>
                {c.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
            <div style={{ fontSize: 12, color: '#6b7280', marginBottom: 4 }}>{c.location}</div>
            <div data-font="mono" style={{ fontSize: 11, color: '#9ca3af', marginBottom: 16, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.url}</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={() => openEdit(c)} style={{ flex: 1, padding: '7px', background: '#f5f5f5', border: '1px solid #d1d5db', borderRadius: 7, fontSize: 12, fontWeight: 500, cursor: 'pointer', color: '#374151', transition: 'all 0.15s' }} onMouseEnter={e => (e.currentTarget.style.borderColor = '#0f5a3a')} onMouseLeave={e => (e.currentTarget.style.borderColor = '#d1d5db')}>Edit</button>
              <button onClick={() => remove(c.id)} style={{ flex: 1, padding: '7px', background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 7, fontSize: 12, fontWeight: 500, cursor: 'pointer', color: '#dc2626', transition: 'all 0.15s' }} onMouseEnter={e => (e.currentTarget.style.background = '#fee2e2')} onMouseLeave={e => (e.currentTarget.style.background = '#fef2f2')}>Delete</button>
            </div>
          </div>
        ))}
        {cameras.length === 0 && (
          <div style={{ gridColumn: '1/-1', textAlign: 'center', padding: '60px 0', color: '#9ca3af', fontSize: 14 }}>No cameras configured yet</div>
        )}
      </div>
    </div>
  )
}
