import client from '../../shared/client';

export interface LoginRequest { username: string; password: string; }
export interface UserInfo { id: number; username: string; display_name: string; role: string; email?: string; enabled: boolean; created_at: string; updated_at: string; }
export interface LoginResponse { token: string; user: UserInfo; }
export interface UserCreate { username: string; password: string; display_name: string; role: string; email?: string; }
export interface UserUpdate { display_name?: string; role?: string; email?: string; enabled?: boolean; password?: string; }

export const authApi = {
  login: (data: LoginRequest) => client.post<LoginResponse>('/api/auth/login', data).then(r => r.data),
  logout: () => client.post('/api/auth/logout'),
  me: () => client.get<UserInfo>('/api/auth/me').then(r => r.data),
  listUsers: (page = 1, pageSize = 20) => client.get('/api/users', { params: { page, page_size: pageSize } }).then(r => r.data),
  createUser: (data: UserCreate) => client.post('/api/users', data).then(r => r.data),
  updateUser: (id: number, data: UserUpdate) => client.put(`/api/users/${id}`, data).then(r => r.data),
  deleteUser: (id: number) => client.delete(`/api/users/${id}`).then(r => r.data),
  downloadLog: async (date?: string) => {
    const token = localStorage.getItem('token');
    const params = new URLSearchParams();
    if (date) params.set('date', date);
    const res = await fetch(`http://localhost:8000/api/logs/download?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error('下载失败');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = date ? `operation.log.${date}` : 'operation.log';
    a.click();
    URL.revokeObjectURL(url);
  },
};
