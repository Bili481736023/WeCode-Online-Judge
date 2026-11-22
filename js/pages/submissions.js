import { submissionApi } from '../api.js';
import { store } from '../store.js';
import { escapeHtml, formatTime } from '../utils.js';
import { loadingHtml, emptyHtml } from '../ui.js';

let bound = false;

export async function renderSubmissions() {
    const wrap = document.getElementById('submissionTableWrap');
    wrap.innerHTML = loadingHtml('加载提交记录...');

    if (!bound) {
        document.getElementById('refreshSubmissions').onclick = renderSubmissions;
        bound = true;
    }

    if (!store.isLoggedIn()) {
        wrap.innerHTML = emptyHtml('请先登录');
        return;
    }

    try {
        store.submissions = await submissionApi.list();
    } catch (err) {
        wrap.innerHTML = emptyHtml('加载失败', err.message);
        return;
    }

    if (!store.submissions.length) {
        wrap.innerHTML = emptyHtml('暂无提交记录', '快去刷题吧！');
        return;
    }

    const list = [...store.submissions].reverse();
    wrap.innerHTML = `
        <table>
            <thead>
                <tr>
                    <th>题目</th><th>语言</th><th>状态</th><th>时间</th><th>代码预览</th>
                </tr>
            </thead>
            <tbody>
                ${list.slice(0, 50).map(s => {
                    const cls = s.status === 'Accepted' ? 'accepted'
                        : s.status === 'Wrong Answer' ? 'wrong' : 'pending';
                    const preview = (s.code || '').slice(0, 60).replace(/\n/g, ' ');
                    return `
                        <tr>
                            <td>${escapeHtml(s.problemTitle || '#' + s.problemId)}</td>
                            <td>${escapeHtml(s.language || '')}</td>
                            <td><span class="status-badge ${cls}">${escapeHtml(s.status || '')}</span></td>
                            <td>${escapeHtml(formatTime(s.createdAt))}</td>
                            <td style="font-family:monospace;font-size:12px;color:#475569;">${escapeHtml(preview)}</td>
                        </tr>
                    `;
                }).join('')}
            </tbody>
        </table>
        <p style="margin-top:12px;font-size:13px;color:#94a3b8;">共 ${list.length} 条，显示最近 50 条</p>
    `;
}