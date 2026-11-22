import { store } from './store.js';
import { renderNav } from './ui.js';
import { initAuthPage } from './pages/auth.js';
import { renderProblems } from './pages/problems.js';
import { renderDetail } from './pages/detail.js';
import { renderSubmissions } from './pages/submissions.js';
import { renderProfile } from './pages/profile.js';

const PUBLIC_PAGES = ['login', 'register'];

function parseHash() {
    const raw = location.hash.replace(/^#\/?/, '') || 'problems';
    const parts = raw.split('/');
    return { name: parts[0], param: parts[1] || null };
}

export function navigate(name, param) {
    location.hash = param ? `#/${name}/${param}` : `#/${name}`;
}

export function showPage(name) {
    document.querySelectorAll('.page').forEach((el) => el.classList.remove('active'));
    const target = document.getElementById(`page-${name}`);
    if (target) target.classList.add('active');
}

async function handleRoute() {
    const { name, param } = parseHash();

    if (!store.isLoggedIn() && !PUBLIC_PAGES.includes(name)) {
        location.hash = '#/login';
        return;
    }
    if (store.isLoggedIn() && PUBLIC_PAGES.includes(name)) {
        location.hash = '#/problems';
        return;
    }

    switch (name) {
        case 'login':
        case 'register':
            showPage(name);
            initAuthPage(name);
            break;
        case 'problems':
            showPage('problems');
            renderProblems();
            break;
        case 'problem':
            showPage('detail');
            renderDetail(param);
            break;
        case 'submissions':
            showPage('submissions');
            renderSubmissions();
            break;
        case 'profile':
            showPage('profile');
            renderProfile();
            break;
        default:
            location.hash = '#/problems';
    }

    renderNav();
    window.scrollTo({ top: 0 });
}

export function initRouter() {
    window.addEventListener('hashchange', handleRoute);
    handleRoute();
}