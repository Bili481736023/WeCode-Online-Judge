import { authApi } from '../api.js';
import { store } from '../store.js';
import { setAuthMsg, toast } from '../ui.js';

let bound = false;

export function initAuthPage(page) {
    if (!bound) {
        document.getElementById('loginForm').addEventListener('submit', onLogin);
        document.getElementById('registerForm').addEventListener('submit', onRegister);
        bound = true;
    }
    document.getElementById('loginMsg').className = 'auth-msg';
    document.getElementById('registerMsg').className = 'auth-msg';
}

async function onLogin(e) {
    e.preventDefault();
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    const msgEl = document.getElementById('loginMsg');
    if (!username || !password) {
        return setAuthMsg(msgEl, '请填写完整信息', 'error');
    }
    try {
        const user = await authApi.login(username, password);
        // Cookie 已由后端 Set-Cookie 下发，这里只保存内存用户信息
        store.setUser(user);
        toast('登录成功', 'success');
        location.hash = '#/problems';
    } catch (err) {
        setAuthMsg(msgEl, err.message, 'error');
    }
}

async function onRegister(e) {
    e.preventDefault();
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value.trim();
    const email = document.getElementById('regEmail').value.trim();
    const msgEl = document.getElementById('registerMsg');
    if (username.length < 2) return setAuthMsg(msgEl, '用户名至少 2 个字符', 'error');
    if (password.length < 4) return setAuthMsg(msgEl, '密码至少 4 个字符', 'error');
    try {
        await authApi.register(username, password, email);
        setAuthMsg(msgEl, '注册成功！请登录', 'success');
        document.getElementById('registerForm').reset();
        setTimeout(() => { location.hash = '#/login'; }, 600);
    } catch (err) {
        setAuthMsg(msgEl, err.message, 'error');
    }
}