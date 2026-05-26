import { useState, type FormEvent } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../api'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const { data } = await api.post('/auth/login', { email, password })
      localStorage.setItem('token', data.access_token)
      if (data.user) {
        localStorage.setItem('role', data.user.role)
        localStorage.setItem('user_name', data.user.full_name)
        localStorage.setItem('user_email', data.user.email)
      }
      navigate('/')
    } catch {
      setError('Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', background: '#f0fdf4' }}>
      {/* Left panel */}
      <div style={{ width: 420, background: '#0d4a52', display: 'flex', flexDirection: 'column', justifyContent: 'center', padding: '60px 48px' }}>
        <h1 style={{ color: '#ffffff', fontSize: 28, fontWeight: 700, margin: '0 0 12px', lineHeight: 1.3 }}>Intelligent Detection and Alerts For Threat Security</h1>
        <p style={{ color: '#9ca3af', fontSize: 14, lineHeight: 1.7, margin: 0 }}>
          Real-time monitoring and threat detection for ATM security.
        </p>
        <div style={{ marginTop: 48, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {['Live monitoring', 'AI threat detection', 'Instant alerts'].map(f => (
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
          <h2 style={{ fontSize: 22, fontWeight: 700, color: '#1f2937', margin: '0 0 6px' }}>Sign in</h2>
          <p style={{ color: '#6b7280', margin: '0 0 32px', fontSize: 14 }}>Enter your credentials to access the dashboard</p>

          <form onSubmit={submit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Email address</label>
              <input
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                placeholder="admin@company.com"
                style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 14, color: '#1f2937', background: '#f9fafb', outline: 'none', transition: 'all 0.15s' }}
                onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: 13, fontWeight: 500, color: '#374151', marginBottom: 6 }}>Password</label>
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                style={{ width: '100%', padding: '10px 14px', border: '1.5px solid #f0f1f3', borderRadius: 8, fontSize: 14, color: '#1f2937', background: '#f9fafb', outline: 'none', transition: 'all 0.15s' }}
                onFocus={e => (e.currentTarget.style.borderColor = '#0f5a3a')}
                onBlur={e => (e.currentTarget.style.borderColor = '#f0f1f3')}
              />
            </div>
            {error && <p style={{ color: '#dc2626', fontSize: 13, margin: 0, fontWeight: 500 }}>{error}</p>}
            <button
              type="submit"
              disabled={loading}
              style={{ padding: '11px', background: loading ? '#b0e0c0' : '#0f5a3a', color: '#ffffff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', transition: 'all 0.15s' }}
              onMouseEnter={e => !loading && (e.currentTarget.style.background = '#0d4a2f')}
              onMouseLeave={e => !loading && (e.currentTarget.style.background = '#0f5a3a')}
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
            
            <div style={{ textAlign: 'center', fontSize: 13 }}>
              Don't have an account?{' '}
              <Link to="/signup" style={{ color: '#4ade80', textDecoration: 'none', fontWeight: 600 }}>
                Sign up
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}
