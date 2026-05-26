import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

api.interceptors.response.use(r => r, err => {
  if (err.response?.status === 401) {
    localStorage.removeItem('token')
    window.location.href = '/login'
  }
  return Promise.reject(err)
})

export default api

export interface Alert {
  id: number; cam_id: string; level: string
  // NEW: Supervised fields
  alert_type?: string; object_detected?: string; confidence?: number; detection_source?: string; track_id?: number
  // Legacy fields
  ae_level: string; yolo_level: string; beh_level: string
  ae_error: number; top_detection: string | null
  n_detections: number; loiter_sec: number
  frame_path: string | null; video_path: string | null
  timestamp: string; acknowledged: boolean; acknowledged_at: string | null
  comment: string | null; manager_comment: string | null; is_false_alert: boolean
  escalated: boolean; escalated_at: string | null
}

export interface AlertStats {
  total: number; high: number; medium: number; low: number
  unacknowledged: number; today: number; by_camera: Record<string, number>
}

export interface Camera {
  id: number; cam_id: string; name: string; url: string
  location: string; latitude: number | null; longitude: number | null
  is_active: boolean; created_at: string
}

export interface User {
  id: number; email: string; full_name: string
  role: string; is_active: boolean; created_at: string
}
