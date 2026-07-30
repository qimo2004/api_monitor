import client from '../../shared/client';

export const userApi = {
  list: (params?: any) => client.get('/api/users', { params }).then(r => r.data),
  create: (data: any) => client.post('/api/users', data).then(r => r.data),
  update: (id: number, data: any) => client.put(`/api/users/${id}`, data).then(r => r.data),
  delete: (id: number) => client.delete(`/api/users/${id}`).then(r => r.data),
};
