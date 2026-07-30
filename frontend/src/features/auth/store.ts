import { create } from 'zustand';
import type { UserInfo } from './api';

interface AuthState {
  token: string | null;
  user: UserInfo | null;
  setAuth: (token: string, user: UserInfo) => void;
  logout: () => void;
  isAuthenticated: () => boolean;
  hasRole: (roles: string[]) => boolean;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token'),
  user: JSON.parse(localStorage.getItem('user') || 'null'),
  setAuth: (token, user) => {
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(user));
    set({ token, user });
  },
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    set({ token: null, user: null });
  },
  isAuthenticated: () => !!get().token,
  hasRole: (roles) => {
    const user = get().user;
    return !!user && roles.includes(user.role);
  },
}));
