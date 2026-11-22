import { problemApi, submissionApi } from '../api.js';
import { store } from '../store.js';
import { escapeHtml, difficultyClass } from '../utils.js';
import { loadingHtml, emptyHtml, toast } from '../ui.js';
import { navigate } from '../router.js';

const filters = {
    keyword: '',
    difficulty: '',
    category: '',
};
let eventsBound = false;

export async function renderProblems() {
    const grid = document.getElementById('problemGrid');
    grid.innerHTML = loadingHtml('加载题目中...');

    try {
        store.problems = await problemApi.list();
        if (store.isLoggedIn()) {
            try { store.submissions = await submissionApi.list(); } catch {}
        }
    } catch (err) {
        grid.innerHTML = emptyHtml('加载失败', err.message);
        return;
    }

    populateFilters();
    renderList();

    if (!eventsBound) {
        bindEvents();
        eventsBound = true;
    }
}

function populateFilters() {
    const diffSelect = document.getElementById('filterDifficulty');
    const catSelect = document.getElementById('filterCategory');

    const difficulties = [...new Set(store.problems.map(p => p.difficulty).filter(Boolean))];
    diffSelect.innerHTML = '<option value="">全部难度</option>' +
        difficulties.map(d => `<option value="${escapeHtml(d)}">${escapeHtml(d)}</option>`).join('');

    const categories = [...new Set(store.problems.map(p => p.category).filter(Boolean))];
    catSelect.innerHTML = '<option value="">全部分类</option>' +
        categories.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join('');

    diffSelect.value = filters.difficulty;
    catSelect.value = filters.category;
}

function renderList() {
    const grid = document.getElementById('problemGrid');
    const countEl = document.getElementById('problemCount');

    const solved = new Set();
    const attempted = new Set();
    store.submissions.forEach(s => {
        if (s.status === 'Accepted') solved.add(s.problemId);
        else attempted.add(s.problemId);
    });

    const list = store.problems.filter(p => {
        if (filters.difficulty && p.difficulty !== filters.difficulty) return false;
        if (filters.category && p.category !== filters.category) return false;
        if (filters.keyword) {
            const kw = filters.keyword.toLowerCase();
            if (!p.title.toLowerCase().includes(kw) && !(p.category || '').toLowerCase().includes(kw)) {
                return false;
            }
        }
        return true;
    });

    countEl.textContent = `共 ${list.length} 题`;

    if (!list.length) {
        grid.innerHTML = emptyHtml('暂无题目', '请等待管理员添加题目');
        return;
    }

    grid.innerHTML = list.map(p => {
        let status = '未做';
        if (solved.has(p.id)) status = '已通过';
        else if (attempted.has(p.id)) status = '已尝试';

        return `
            <div class="problem-card" data-id="${p.id}">
                <div class="title-row">
                    <h3>${escapeHtml(p.title)}</h3>
                    <span class="difficulty ${difficultyClass(p.difficulty)}">${escapeHtml(p.difficulty || '未知')}</span>
                </div>
                <div class="meta">
                    <span>分类：${escapeHtml(p.category || '未分类')}</span>
                    <span>状态：${status}</span>
                </div>
                <div class="meta" style="margin-top:8px;">
                    <span>#${escapeHtml(String(p.id))}</span>
                </div>
            </div>
        `;
    }).join('');

    grid.querySelectorAll('.problem-card').forEach(card => {
        card.onclick = () => navigate('problem', card.dataset.id);
    });
}

function bindEvents() {
    document.getElementById('searchInput').addEventListener('input', e => {
        filters.keyword = e.target.value.trim();
        renderList();
    });
    document.getElementById('filterDifficulty').addEventListener('change', e => {
        filters.difficulty = e.target.value;
        renderList();
    });
    document.getElementById('filterCategory').addEventListener('change', e => {
        filters.category = e.target.value;
        renderList();
    });
}