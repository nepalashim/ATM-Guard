import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import Signup from './pages/Signup'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import AlertHistory from './pages/AlertHistory'
import CameraManager from './pages/CameraManager'
import ManagerDashboard from './pages/ManagerDashboard'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  return localStorage.getItem('token') ? <>{children}</> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="history" element={<AlertHistory />} />
          <Route path="cameras" element={<CameraManager />} />
          <Route path="manager" element={<ManagerDashboard />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
