import { Outlet, NavLink, useNavigate } from 'react-router-dom'

const links = [
  { to: '/',         label: 'Dashboard',     icon: '▣' },
  { to: '/history',  label: 'Alert History', icon: '≡' },
  { to: '/cameras',  label: 'Cameras',       icon: '◉' },
  { to: '/manager',  label: 'Reports',       icon: '▦' },
]

export default function Layout() {
  const navigate = useNavigate()
  const userName = localStorage.getItem('user_name') ?? 'User'
  const userRole = localStorage.getItem('role') ?? 'supervisor'

  function logout() {
    localStorage.removeItem('token')
    localStorage.removeItem('role')
    localStorage.removeItem('user_name')
    localStorage.removeItem('user_email')
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen" style={{ background: '#f0fdf4' }}>
      {/* Sidebar */}
      <aside style={{ width: 260, background: 'linear-gradient(135deg, #d4eff4 0%, #030d10 100%)', display: 'flex', flexDirection: 'column', flexShrink: 0, boxShadow: '2px 0 8px rgba(0,0,0,0.15)' }}>
        {/* Logo */}
        <div style={{ padding: '32px 28px 24px', borderBottom: '1px solid rgba(77, 202, 128, 0.15)' }}>
          <div style={{ color: '#0d4a2f', fontWeight: 800, fontSize: 18, letterSpacing: 0.5, lineHeight: 1.2 }}>ATM</div>
          <div style={{ color: '#0d4a2f', fontWeight: 800, fontSize: 18, letterSpacing: 0.5 }}>Guardian</div>
          <div style={{ color: '#0f5a3a', fontSize: 12, marginTop: 6, fontWeight: 500, letterSpacing: 0.5, textTransform: 'uppercase' }}>Security Monitoring</div>
        </div>

        {/* User info */}
        <div style={{ padding: '20px 28px', borderBottom: '1px solid rgba(77, 202, 128, 0.1)', background: 'rgba(15, 90, 58, 0.08)' }}>
          <div style={{ color: '#1f2937', fontSize: 14, fontWeight: 700 }}>{userName}</div>
          <div style={{ color: '#6b7280', fontSize: 12, marginTop: 3, textTransform: 'capitalize', fontWeight: 500 }}>{userRole}</div>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '20px 16px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {links.map(l => (
            <NavLink
              key={l.to}
              to={l.to}
              end={l.to === '/'}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: 12,
                padding: '12px 16px',
                borderRadius: 10,
                fontSize: 14,
                fontWeight: isActive ? 700 : 500,
                color: isActive ? '#ffffff' : '#1f2937',
                background: isActive ? 'rgba(15, 90, 58, 0.3)' : 'transparent',
                textDecoration: 'none',
                transition: 'all 0.2s ease',
                borderLeft: isActive ? '3px solid #4ade80' : '3px solid transparent',
                paddingLeft: isActive ? '13px' : '16px',
              })}
              onMouseEnter={(e) => {
                if (!e.currentTarget.className.includes('active')) {
                  e.currentTarget.style.background = 'rgba(77, 202, 128, 0.15)'
                  e.currentTarget.style.color = '#0f5a3a'
                }
              }}
              onMouseLeave={(e) => {
                if (!e.currentTarget.className.includes('active')) {
                  e.currentTarget.style.background = 'transparent'
                  e.currentTarget.style.color = '#1f2937'
                }
              }}
            >
              <span style={{ fontSize: 18, display: 'flex', alignItems: 'center', justifyContent: 'center', width: 20 }}>{l.icon}</span>
              <span>{l.label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Sign out */}
        <div style={{ padding: '16px 16px', borderTop: '1px solid rgba(77, 202, 128, 0.1)' }}>
          <button
            onClick={logout}
            style={{ width: '100%', textAlign: 'left', padding: '12px 16px', background: 'transparent', border: '1px solid rgba(220, 38, 38, 0.2)', color: '#9ca3af', fontSize: 14, fontWeight: 600, cursor: 'pointer', borderRadius: 10, transition: 'all 0.2s ease' }}
            onMouseEnter={e => {
              e.currentTarget.style.background = 'rgba(220, 38, 38, 0.1)'
              e.currentTarget.style.color = '#dc2626'
              e.currentTarget.style.borderColor = 'rgba(220, 38, 38, 0.4)'
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = 'transparent'
              e.currentTarget.style.color = '#9ca3af'
              e.currentTarget.style.borderColor = 'rgba(220, 38, 38, 0.2)'
            }}
          >
            Sign out
          </button>
        </div>
      </aside>

      {/* Content */}
      <main style={{ flex: 1, overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}
