import { http } from './http'

export const recordsApi = {
  list(params = {}) {
    return http.get('/records', { params })
  },
  summary(params = {}) {
    return http.get('/records/summary', { params })
  },
  create(payload) {
    return http.post('/records', payload)
  }
}
