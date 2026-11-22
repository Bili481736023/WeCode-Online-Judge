import { store } from './store.js';
import { initRouter } from './router.js';
import { authApi } from './api.js';
import { renderNav } from './ui.js';

async function init() {
    // 尝试用 Cookie 恢复会话
    try {
        const me = await authApi.me();
        if (me && me.id) {
            store.setUser(me);
        }
    } catch (err) {
        // 未登录是正常情况（401），无需处理
        store.clearUser();
    }

    renderNav();
    initRouter();

    const logoIcon = document.getElementById('logoIcon');
    if (logoIcon) {
        const img = document.createElement('img');
        img.src = 'assets/icons/icon-logo.svg';
        img.alt = 'WeCode OJ';
        logoIcon.appendChild(img);
    }
}

document.addEventListener('DOMContentLoaded', init);