export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? (
  typeof window !== 'undefined' && (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1')
    ? 'http://localhost:8000'
    : ''
);

const TOKEN_KEY = 'recruitiq_access_token';
const USER_KEY = 'recruitiq_user_profile';

export const getAuthToken = () => {
  return localStorage.getItem(TOKEN_KEY);
};

export const getAuthUser = () => {
  const user = localStorage.getItem(USER_KEY);
  try {
    return user ? JSON.parse(user) : null;
  } catch {
    return null;
  }
};

export const setAuthSession = (token, user) => {
  localStorage.setItem(TOKEN_KEY, token);
  if (user) {
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }
};

export const clearAuthSession = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

// Global Fetch Interceptor to attach Bearer token to all RecruitIQ API calls
const originalFetch = window.fetch;
window.fetch = async (...args) => {
  let [resource, config] = args;
  if (typeof resource === 'string' && (resource.startsWith(API_BASE) || resource.startsWith('/'))) {
    const token = getAuthToken();
    if (token) {
      config = config || {};
      const headers = new Headers(config.headers || {});
      if (!headers.has('Authorization')) {
        headers.set('Authorization', `Bearer ${token}`);
      }
      config.headers = headers;
    }
  }
  const response = await originalFetch(resource, config);
  if (
    response.status === 401 &&
    typeof resource === 'string' &&
    resource.startsWith(API_BASE) &&
    !resource.includes('/auth/')
  ) {
    clearAuthSession();
    window.dispatchEvent(new Event('auth:unauthorized'));
  }
  return response;
};
