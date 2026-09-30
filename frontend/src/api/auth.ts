const TOKEN_KEY = 'paper_translator_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export interface AuthStatus {
  authenticated: boolean;
  auth_enabled: boolean;
}

export async function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const token = getToken();
  const headers = new Headers(init.headers || {});

  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(input, {
    ...init,
    headers,
    credentials: 'same-origin',
  });

  if (response.status === 401) {
    clearToken();
    window.dispatchEvent(new CustomEvent('auth:unauthorized'));
  }

  return response;
}

export async function login(password: string): Promise<{ token: string }> {
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password }),
    credentials: 'same-origin',
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '密码错误，解锁失败' }));
    throw new Error(err.detail || '密码错误');
  }

  const data = await res.json();
  if (data.token) {
    setToken(data.token);
  }
  return data;
}

export async function logout(): Promise<void> {
  try {
    await fetch('/api/auth/logout', {
      method: 'POST',
      credentials: 'same-origin',
    });
  } catch (err) {
    console.error('退出请求失败:', err);
  } finally {
    clearToken();
  }
}

export async function getCurrentUser(): Promise<AuthStatus> {
  const token = getToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch('/api/auth/me', {
    headers,
    credentials: 'same-origin',
  });

  if (!res.ok) {
    return { authenticated: false, auth_enabled: true };
  }

  return res.json();
}
