import { store } from './store.js';
import { authApi } from './api.js';
import { toast, confirmDialog } from './ui.js';
import { renderAdminPanel, initAdminPage } from './pages/admin.js';

async function init() {
    try {
        const me = await authApi.me();
        if (!me.isAdmin) {
            toast('权限不足', 'error');
            setTimeout(() => { location.href = 'index.html'; }, 800);
            return;
        }
        store.setUser(me);
    } catch (err) {
        location.href = 'index.html#/login';
        return;
    }

    renderAdminNav();
    initAdminPage();
    renderAdminPanel('users');
}

function renderAdminNav() {
    const nav = document.getElementById('navActions');
    const u = store.currentUser;
    nav.innerHTML = `
        <span class="user-info">
            <img src="assets/icons/icon-user.svg" alt="" />
            ${u.username} (管理员)
        </span>
        <a href="index.html" class="btn btn-outline btn-sm">返回主站</a>
        <button class="btn btn-danger btn-sm" id="navLogout">退出</button>
    `;
    nav.querySelector('#navLogout').onclick = async () => {
        if (await confirmDialog('确定退出管理后台吗？')) {
            try { await authApi.logout(); } catch {}
            store.clearUser();
            location.href = 'index.html#/login';
        }
    };
}

function loadLogo() {
    const logoIcon = document.getElementById('logoIcon');
    if (!logoIcon) return;
    const img = document.createElement('img');
    img.src = 'assets/icons/icon-logo.svg';
    img.alt = 'WeCode OJ';
    logoIcon.appendChild(img);
}

document.addEventListener('DOMContentLoaded', () => {
    loadLogo();
    init();
});