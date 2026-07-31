import client from '../../shared/client';

export interface ApiItem {
  id: number; name: string; url: string; method: string;
  headers?: string; body?: string; body_type?: string; timeout: number;
  expected_status: number; expected_response_time: number;
  check_interval: number; enabled: boolean;
  group_name?: string; tags?: string;
  last_status?: string | null; last_response_time_ms?: number | null;
  created_at: string; updated_at: string;
}
export interface ApiCreate {
  name: string; url: string; method: string;
  headers?: string; body?: string; body_type?: string; timeout?: number;
  expected_status?: number; expected_response_time?: number;
  check_interval?: number; enabled?: boolean;
  group_name?: string; tags?: string;
}
export interface ApiUpdate extends Partial<ApiCreate> {}

export const apiApi = {
  list: (params?: any) => client.get('/api/apis', { params }).then(r => r.data),
  get: (id: number) => client.get<ApiItem>(`/api/apis/${id}`).then(r => r.data),
  create: (data: ApiCreate) => client.post('/api/apis', data).then(r => r.data),
  update: (id: number, data: ApiUpdate) => client.put(`/api/apis/${id}`, data).then(r => r.data),
  delete: (id: number) => client.delete(`/api/apis/${id}`).then(r => r.data),
  check: (id: number, custom?: any) => client.post(`/api/apis/${id}/check`, custom || undefined).then(r => r.data),
  status: () => client.get('/api/apis/status').then(r => r.data),
  batchImport: (items: { name: string; url: string; method?: string; group_name?: string; headers?: string; body?: string; body_type?: string }[]) => client.post('/api/apis/batch', items).then(r => r.data),
  batchCheckInterval: (ids: number[], check_interval: number) => client.put('/api/apis/batch/check-interval', { ids, check_interval }).then(r => r.data),
  batchEnabled: (ids: number[], enabled: boolean) => client.put('/api/apis/batch/enabled', { ids, enabled }).then(r => r.data),
  batchDelete: (ids: number[]) => client.post('/api/apis/batch/delete', { ids }).then(r => r.data),
  getAuthorizations: () => client.get('/api/apis/authorizations').then(r => r.data),
  updateAuthorization: (apiId: number, userIds: number[]) => client.put(`/api/apis/${apiId}/authorizations`, { user_ids: userIds }).then(r => r.data),
};
