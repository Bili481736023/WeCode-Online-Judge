import { store } from './store.js';
import { escapeHtml } from './utils.js';
import { authApi } from './api.js';

export function toast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const el = document.createElement('div');
    el.className = `toast ${type}`;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 2600);
}

export function confirmDialog(message) {
    return new Promise((resolve) => {
        const root = document.getElementById('modalRoot');
        root.innerHTML = `
            <div class="modal-mask">
                <div class="modal">
                    <h3>确认操作</h3>
                    <p>${escapeHtml(message)}</p>
                    <div class="actions">
                        <button class="btn btn-outline" id="modalCancel">取消</button>
                        <button class="btn btn-danger" id="modalOk">确定</button>
                    </div>
                </div>
            </div>
        `;
        root.querySelector('#modalCancel').onclick = () => {
            root.innerHTML = '';
            resolve(false);
        };
        root.querySelector('#modalOk').onclick = () => {
            root.innerHTML = '';
            resolve(true);
        };
    });
}

export function renderNav() {
    const nav = document.getElementById('navActions');
    if (!nav) return;

    if (store.isLoggedIn()) {
        const u = store.currentUser;
        let buttons = `
            <span class="user-info">
                <img src="assets/icons/icon-user.svg" alt="" />
                ${escapeHtml(u.username)}${u.isAdmin ? ' (管理员)' : ''}
            </span>
            <a href="#/problems" class="btn btn-outline btn-sm">题库</a>
        `;
        if (u.isAdmin) {
            buttons += `<a href="back_platform.html" class="btn btn-outline btn-sm">管理</a>`;
        }
        buttons += `
            <a href="#/submissions" class="btn btn-outline btn-sm">记录</a>
            <a href="#/profile" class="btn btn-outline btn-sm">进度</a>
            <button class="btn btn-danger btn-sm" id="navLogout">退出</button>
        `;
        nav.innerHTML = buttons;
        nav.querySelector('#navLogout').onclick = async () => {
            if (await confirmDialog('确定要退出吗？')) {
                try {
                    await authApi.logout();
                } catch {
                    // 忽略网络错误，本地状态照样清空
                }
                store.clearUser();
                location.hash = '#/login';
                renderNav();
            }
        };
    } else {
        nav.innerHTML = `
            <a href="#/login" class="btn btn-primary">登录</a>
            <a href="#/register" class="btn btn-outline">注册</a>
        `;
    }
}

export function setAuthMsg(el, msg, type) {
    if (!el) return;
    el.textContent = msg;
    el.className = `auth-msg ${type}`;
}

export function loadingHtml(text = '加载中...') {
    return `
        <div class="loading">
            <div class="spinner"></div>
            <div>${escapeHtml(text)}</div>
        </div>
    `;
}

export function emptyHtml(title, subtitle = '') {
    return `
        <div class="empty-state">
            <h3>${escapeHtml(title)}</h3>
            ${subtitle ? `<p>${escapeHtml(subtitle)}</p>` : ''}
        </div>
    `;
}