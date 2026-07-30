import client from '../../shared/client';

export const statsApi = {
  dashboard: () => client.get('/api/dashboard').then(r => r.data),
  apiStats: (apiId: number, days = 30) => client.get(`/api/apis/${apiId}/stats`, { params: { days } }).then(r => r.data),
  topSlow: (limit = 10) => client.get('/api/top-slow', { params: { limit } }).then(r => r.data),
  topUnstable: (limit = 10) => client.get('/api/top-unstable', { params: { limit } }).then(r => r.data),
  allApisStats: (days = 7) => client.get('/api/apis/stats/all', { params: { days } }).then(r => r.data),
  compareStats: (apiIds: number[], days = 7) => client.post('/api/apis/stats/compare', { api_ids: apiIds, days }).then(r => r.data),
  exportReport: (params?: any) => client.get('/api/reports/export', { params, responseType: 'blob' }).then(r => r.data),
};
