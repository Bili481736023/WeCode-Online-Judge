import { problemApi, submissionApi } from '../api.js';
import { store } from '../store.js';
import { escapeHtml, formatTime } from '../utils.js';
import { loadingHtml, emptyHtml } from '../ui.js';

export async function renderProfile() {
    if (!store.isLoggedIn()) return;

    document.getElementById('profileUsername').textContent = store.currentUser.username;
    const statsGrid = document.getElementById('statsGrid');
    const recentDiv = document.getElementById('recentSubmissions');

    statsGrid.innerHTML = loadingHtml('加载中...');
    recentDiv.innerHTML = '';

    try {
        const [problems, submissions] = await Promise.all([
            problemApi.list(),
            submissionApi.list(),
        ]);
        store.problems = problems;
        store.submissions = submissions;

        const total = problems.length;
        const solved = new Set(submissions.filter(s => s.status === 'Accepted').map(s => s.problemId)).size;
        const attempted = new Set(submissions.map(s => s.problemId)).size;

        statsGrid.innerHTML = `
            <div class="stat-item"><div class="number blue">${total}</div><div class="label">总题目</div></div>
            <div class="stat-item"><div class="number green">${solved}</div><div class="label">已通过</div></div>
            <div class="stat-item"><div class="number orange">${Math.max(0, attempted - solved)}</div><div class="label">尝试中</div></div>
            <div class="stat-item"><div class="number">${total ? Math.round(solved / total * 100) : 0}%</div><div class="label">完成率</div></div>
        `;

        const recent = submissions.slice(-5).reverse();
        if (!recent.length) {
            recentDiv.innerHTML = '<p style="color:#94a3b8;font-size:14px;">暂无提交记录</p>';
            return;
        }
        recentDiv.innerHTML = recent.map(s => {
            const cls = s.status === 'Accepted' ? 'accepted' : 'wrong';
            return `
                <div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid #f1f5f9;font-size:14px;">
                    <span>${escapeHtml(s.problemTitle || '#' + s.problemId)}
                        <span class="status-badge ${cls}">${escapeHtml(s.status || '')}</span>
                    </span>
                    <span style="color:#94a3b8;">${escapeHtml(formatTime(s.createdAt))}</span>
                </div>
            `;
        }).join('');
    } catch (err) {
        statsGrid.innerHTML = emptyHtml('加载失败', err.message);
    }
}