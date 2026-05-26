import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../api'

export default function Signup() {
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('supervisor')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.post('/auth/register', { 
        full_name: fullName,
        email, 
        password,
        role
      })
      
      // Auto-login after signup
      const loginData = await api.post('/auth/login', { email, password })
      localStorage.setItem('token', loginData.data.access_token)
      localStorage.setItem('role', loginData.data.user.role)
      localStorage.setItem('user_name', loginData.data.user.full_name)
      localStorage.setItem('user_email', loginData.data.user.email)
      
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Signup failed. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: '#f0fdf4' }}>
      {/* Left panel */}
      <div style={{ width: 420, background: '#0d4a52', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '60px 48px' }}>
        <h1 style={{ color: '#ffffff', fontSize: 28, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.3 }}>Join the Security Platform</h1>
        <p style={{ color: '#9ca3af', fontSize: 14, lineHeight: 1.7, margin: 0 }}>
          Create your account as a Supervisor or Manager to start monitoring threats in real-time.
        </p>
        <div style={{ marginTop: 48, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {['Real-time alerts', 'Role-based access', 'Team collaboration'].map(f => (
            <div key={f} style={{ display: 'flex', alignItems: 'center', gap: 10, color: '#9ca3af', fontSize: 13 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80', flexShrink: 0 }} />
              {f}
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 40 }}>
        <div style={{ width: '100%', maxWidth: 380 }}>
          <h2 style={{ fontSize: 22, fontWeight: 700, color: '#1f2937', margin: '0 0 6px' }}>Create account</h2>
          <p style={{ color: '#6b7280', margin: '0 0 24px', fontSize: 14 }}>Sign up to get started</p>

          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Full Name */}
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Full name</label>
              <input
                type="text"
                value={fullName}
                onChange={e => setFullName(e.target.value)}
                required
                placeholder="John Supervisor"
                style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 14, color: '#1f2937', background: '#f9fafb', outline: 'none', transition: 'all 0.15s' }}
                onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')}
              />
            </div>

            {/* Email */}
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Email address</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="john@company.com"
                style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 14, color: '#1f2937', background: '#f9fafb', outline: 'none', transition: 'all 0.15s' }}
                onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')}
              />
            </div>

            {/* Password */}
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                placeholder="••••••••"
                style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 14, color: '#1f2937', background: '#f9fafb', outline: 'none', transition: 'all 0.15s' }}
                onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')}
              />
            </div>

            {/* Role Selection */}
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 10 }}>Account type</label>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {/* Supervisor Option */}
                <label style={{
                  padding: '12px 14px',
                  border: '1.5px solid ' + (role === 'supervisor' ? '#0f5a3a' : '#f0f1f3'),
                  borderRadius: 8,
                  background: role === 'supervisor' ? '#d1fae5' : '#f9fafb',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}>
                  <input
                    type="radio"
                    name="role"
                    value="supervisor"
                    checked={role === 'supervisor'}
                    onChange={e => setRole(e.target.value)}
                    style={{ cursor: 'pointer', accentColor: '#0f5a3a' }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937' }}>Supervisor</div>
                    <div style={{ fontSize: 11, color: '#6b7280' }}>View alerts</div>
                  </div>
                </label>

                {/* Manager Option */}
                <label style={{
                  padding: '12px 14px',
                  border: '1.5px solid ' + (role === 'manager' ? '#0f5a3a' : '#f0f1f3'),
                  borderRadius: 8,
                  background: role === 'manager' ? '#d1fae5' : '#f9fafb',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8
                }}>
                  <input
                    type="radio"
                    name="role"
                    value="manager"
                    checked={role === 'manager'}
                    onChange={e => setRole(e.target.value)}
                    style={{ cursor: 'pointer', accentColor: '#0f5a3a' }}
                  />
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: '#1f2937' }}>Manager</div>
                    <div style={{ fontSize: 11, color: '#6b7280' }}>Full control</div>
                  </div>
                </label>
              </div>
            </div>

            {error && <p style={{ color: '#dc2626', fontSize: 13, margin: 0, fontWeight: 500 }}>{error}</p>}
            
            <button
              type="submit"
              disabled={loading}
              style={{ padding: '11px', background: loading ? '#b0e0c0' : '#0f5a3a', color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}
              onMouseEnter={e => !loading && (e.currentTarget.style.background = '#0d4a2f')}
              onMouseLeave={e => !loading && (e.currentTarget.style.background = '#0f5a3a')}
            >
              {loading ? 'Creating account…' : 'Sign up'}
            </button>

            <div style={{ textAlign: 'center', fontSize: 13 }}>
              Already have an account?{' '}
              <Link to="/login" style={{ color: '#4ade80', textDecoration: 'none', fontWeight: 600 }}>
                Sign in
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
