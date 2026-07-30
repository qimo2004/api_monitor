import client from '../../shared/client';

export interface AlertItem {
  id: number; api_id: number; api_name?: string;
  alert_type: string; message: string; status: string;
  created_at: string; resolved_at?: string;
}

export const alertApi = {
  list: (params?: any) => client.get('/api/alerts', { params }).then(r => r.data),
  resolve: (id: number) => client.post(`/api/alerts/${id}/resolve`).then(r => r.data),
  todayCount: () => client.get('/api/alerts/today-count').then(r => r.data),
};
