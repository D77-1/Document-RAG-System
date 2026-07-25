import axios from 'axios'
import { ElMessage } from 'element-plus'

const service = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 50000, // 50s timeout for large file uploads
})

// Request interceptor
service.interceptors.request.use(
  (config) => {
    // Add token if needed in the future
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Response interceptor
service.interceptors.response.use(
  (response) => {
    const res = response.data
    // You can adjust this based on your backend response structure
    // Assuming backend returns directly the data or a standard wrapper
    return res
  },
  (error) => {
    console.error('Request Error:', error)
    ElMessage({
      message: error.message || 'Request Failed',
      type: 'error',
      duration: 5000,
    })
    return Promise.reject(error)
  }
)

export default service
