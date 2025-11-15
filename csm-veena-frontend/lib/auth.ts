import { JWTPayload } from './api';

const isBrowser = typeof window !== 'undefined';

function safeAtob(input: string): string {
  if (typeof atob === 'function') return atob(input);
  // Node.js fallback
  return Buffer.from(input, 'base64').toString('binary');
}

export function saveToken(token: string): void {
  if (!isBrowser) return;
  try {
    window.localStorage.setItem('access_token', token);
  } catch {
    /* ignore */
  }
}

export function getToken(): string | null {
  if (!isBrowser) return null;
  try {
    return window.localStorage.getItem('access_token');
  } catch {
    return null;
  }
}

export function removeToken(): void {
  if (!isBrowser) return;
  try {
    window.localStorage.removeItem('access_token');
  } catch {
    /* ignore */
  }
}

export function decodeToken(token: string): JWTPayload | null {
  try {
    const base64Url = token.split('.')[1];
    if (!base64Url) return null;
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const binary = safeAtob(base64);
    const jsonPayload = decodeURIComponent(
      binary
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch {
    return null;
  }
}

export function getCurrentUser(): JWTPayload | null {
  const token = getToken();
  if (!token) return null;
  const payload = decodeToken(token);
  if (!payload) return null;
  if (payload.exp * 1000 < Date.now()) {
    removeToken();
    return null;
  }
  return payload;
}

export function isAuthenticated(): boolean {
  if (!isBrowser) return false;
  return getCurrentUser() !== null;
}

export function isAdmin(): boolean {
  if (!isBrowser) return false;
  const user = getCurrentUser();
  return user?.role === 'admin';
}
