import { API_BASE } from './config.js';

export async function api(endpoint, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
    };
    const resp = await fetch(API_BASE + endpoint, {
        ...options,
        headers,
        credentials: 'include',   // ← 带上 HttpOnly Cookie
    });
    let data = null;
    try {
        data = await resp.json();
    } catch {
        data = {};
    }
    if (!resp.ok) {
        throw new Error(data.error || `请求失败 (${resp.status})`);
    }
    return data;
}

export const authApi = {
    login: (username, password) =>
        api('/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
    register: (username, password, email) =>
        api('/register', { method: 'POST', body: JSON.stringify({ username, password, email }) }),
    me: () => api('/me'),
    logout: () => api('/logout', { method: 'POST' }),
};

export const problemApi = {
    list: () => api('/problems'),
    submit: (payload) =>
        api('/submit', { method: 'POST', body: JSON.stringify(payload) }),
};

export const submissionApi = {
    list: () => api('/submissions'),
};

export const adminApi = {
    users: () => api('/users'),
    toggleBan: (userId) =>
        api('/toggle_ban', { method: 'POST', body: JSON.stringify({ userId }) }),
    createUser: (username, password, email) =>
        api('/create_user', { method: 'POST', body: JSON.stringify({ username, password, email }) }),
    addProblem: (data) =>
        api('/add_problem', { method: 'POST', body: JSON.stringify(data) }),
    deleteProblem: (problemId) =>
        api('/delete_problem', { method: 'POST', body: JSON.stringify({ problemId }) }),
    tags: () => api('/tags'),
    addTag: (tag) => api('/add_tag', { method: 'POST', body: JSON.stringify({ tag }) }),
    deleteTag: (tag) => api('/delete_tag', { method: 'POST', body: JSON.stringify({ tag }) }),
};