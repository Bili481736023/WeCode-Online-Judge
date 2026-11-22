import { adminApi, problemApi } from '../api.js';
import { escapeHtml } from '../utils.js';
import { loadingHtml, emptyHtml, toast, confirmDialog } from '../ui.js';

let currentPanel = 'users';
let bound = false;

export function initAdminPage() {
    if (bound) return;
    document.querySelectorAll('.admin-sidebar .menu-item').forEach(item => {
        item.addEventListener('click', () => {
            const panel = item.dataset.panel;
            document.querySelectorAll('.admin-sidebar .menu-item').forEach(el => el.classList.remove('active'));
            item.classList.add('active');
            renderAdminPanel(panel);
        });
    });
    bound = true;
}

export async function renderAdminPanel(panel) {
    currentPanel = panel;
    const root = document.getElementById('adminPanel');
    root.innerHTML = loadingHtml('加载中...');

    try {
        if (panel === 'users') await renderUsersPanel(root);
        else if (panel === 'problems') await renderProblemsPanel(root);
        else if (panel === 'tags') await renderTagsPanel(root);
    } catch (err) {
        root.innerHTML = emptyHtml('加载失败', err.message);
    }
}

/* ==================== 用户管理 ==================== */
async function renderUsersPanel(root) {
    const users = await adminApi.users();
    root.innerHTML = `
        <h2>用户管理</h2>
        <p class="subtitle">查看所有用户，可封禁 / 解封普通用户。</p>
        <div class="admin-list" id="adminUserList">
            ${users.length === 0 ? emptyHtml('暂无用户') :
                users.map(u => `
                    <div class="admin-list-item">
                        <div class="item-main">
                            <strong>${escapeHtml(u.username)}</strong>
                            ${u.isAdmin ? '<span class="item-meta">管理员</span>' : ''}
                            ${u.isBanned ? '<span class="item-meta" style="color:#ef4444;">已封禁</span>' : ''}
                            <span class="item-meta">ID: ${u.id}</span>
                        </div>
                        <div>
                            ${!u.isAdmin ? `
                                <button class="btn btn-sm ${u.isBanned ? 'btn-success' : 'btn-danger'} toggle-ban" data-id="${u.id}" data-banned="${u.isBanned ? 1 : 0}">
                                    ${u.isBanned ? '解封' : '封禁'}
                                </button>
                            ` : '<span class="item-meta">—</span>'}
                        </div>
                    </div>
                `).join('')}
        </div>
        <hr />
        <h4>创建新用户</h4>
        <form id="adminCreateUserForm" class="admin-form">
            <div class="form-group"><label>用户名 *</label><input type="text" id="admNewUsername" placeholder="至少 2 个字符" required /></div>
            <div class="form-group"><label>密码 *</label><input type="text" id="admNewPassword" placeholder="至少 4 个字符" required /></div>
            <div class="form-group"><label>邮箱（可选）</label><input type="email" id="admNewEmail" placeholder="example@email.com" /></div>
            <button type="submit" class="btn btn-success">
                <img src="assets/icons/icon-plus.svg" alt="" class="btn-icon" />
                创建用户
            </button>
        </form>
    `;

    root.querySelectorAll('.toggle-ban').forEach(btn => {
        btn.onclick = async () => {
            const id = parseInt(btn.dataset.id);
            const banned = btn.dataset.banned === '1';
            const action = banned ? '解封' : '封禁';
            if (!await confirmDialog(`确定要${action}该用户吗？`)) return;
            try {
                await adminApi.toggleBan(id);
                toast(`${action}成功`, 'success');
                renderAdminPanel('users');
            } catch (err) {
                toast(err.message, 'error');
            }
        };
    });

    root.querySelector('#adminCreateUserForm').onsubmit = async (e) => {
        e.preventDefault();
        const username = root.querySelector('#admNewUsername').value.trim();
        const password = root.querySelector('#admNewPassword').value.trim();
        const email = root.querySelector('#admNewEmail').value.trim();
        if (username.length < 2) return toast('用户名至少 2 个字符', 'error');
        if (password.length < 4) return toast('密码至少 4 个字符', 'error');
        try {
            await adminApi.createUser(username, password, email);
            toast('创建成功', 'success');
            renderAdminPanel('users');
        } catch (err) {
            toast(err.message, 'error');
        }
    };
}

/* ==================== 题目管理 ==================== */
async function renderProblemsPanel(root) {
    const problems = await problemApi.list();
    root.innerHTML = `
        <h2>题目管理</h2>
        <p class="subtitle">添加新题目，或删除已有题目。题目会以目录形式保存到 problems/ 下。</p>
        <div class="admin-list">
            ${problems.length === 0 ? emptyHtml('暂无题目') :
                problems.map(p => `
                    <div class="admin-list-item">
                        <div class="item-main">
                            <strong>#${p.id} ${escapeHtml(p.title)}</strong>
                            <span class="item-meta">${escapeHtml(p.difficulty || '')} · ${escapeHtml(p.category || '')}</span>
                        </div>
                        <button class="btn btn-danger btn-sm delete-problem" data-id="${p.id}">
                            <img src="assets/icons/icon-wa.svg" alt="" class="btn-icon" />
                            删除
                        </button>
                    </div>
                `).join('')}
        </div>
        <hr />
        <h4>添加题目</h4>
        <form id="adminAddProblemForm" class="admin-form">
            <div class="form-group"><label>标题 *</label><input type="text" id="admTitle" placeholder="例如：两数之和" required /></div>
            <div class="form-group"><label>分类 *</label><input type="text" id="admCategory" placeholder="例如：数组" required /></div>
            <div class="form-group">
                <label>难度 *</label>
                <select id="admDifficulty">
                    <option value="入门">入门</option>
                    <option value="普及-">普及-</option>
                    <option value="普及" selected>普及</option>
                    <option value="普及+/提高-">普及+/提高-</option>
                    <option value="提高">提高</option>
                    <option value="提高+/省选-">提高+/省选-</option>
                    <option value="省选/NOI-">省选/NOI-</option>
                    <option value="NOI/NOI+/CTS">NOI/NOI+/CTS</option>
                </select>
            </div>
            <div class="form-group"><label>描述 *</label><textarea id="admDesc" rows="3" placeholder="详细描述题目..." required></textarea></div>
            <div class="form-group"><label>示例输入</label><input type="text" id="admInput" placeholder="例如：nums = [2,7,11,15], target = 9" /></div>
            <div class="form-group"><label>示例输出</label><input type="text" id="admOutput" placeholder="例如：[0,1]" /></div>
            <div class="form-group"><label>标签（逗号分隔）</label><input type="text" id="admTags" placeholder="例如：数组,哈希表" /></div>
            <div class="form-group"><label>时间限制（毫秒）</label><input type="number" id="admTimeLimit" value="2000" min="500" step="500" /></div>
            <button type="submit" class="btn btn-success">
                <img src="assets/icons/icon-plus.svg" alt="" class="btn-icon" />
                添加题目
            </button>
        </form>
    `;

    root.querySelectorAll('.delete-problem').forEach(btn => {
        btn.onclick = async () => {
            const id = parseInt(btn.dataset.id);
            if (!await confirmDialog(`确定要删除题目 #${id} 吗？该操作不可恢复。`)) return;
            try {
                await adminApi.deleteProblem(id);
                toast('删除成功', 'success');
                renderAdminPanel('problems');
            } catch (err) {
                toast(err.message, 'error');
            }
        };
    });

    root.querySelector('#adminAddProblemForm').onsubmit = async (e) => {
        e.preventDefault();
        const title = root.querySelector('#admTitle').value.trim();
        const category = root.querySelector('#admCategory').value.trim();
        const difficulty = root.querySelector('#admDifficulty').value;
        const description = root.querySelector('#admDesc').value.trim();
        const exampleInput = root.querySelector('#admInput').value.trim() || '无';
        const exampleOutput = root.querySelector('#admOutput').value.trim() || '无';
        const tagsStr = root.querySelector('#admTags').value.trim();
        const timeLimit = parseInt(root.querySelector('#admTimeLimit').value, 10) || 2000;

        if (!title || !category || !description) {
            return toast('请至少填写标题、分类和描述', 'error');
        }

        const tags = tagsStr ? tagsStr.split(',').map(s => s.trim()).filter(Boolean) : [];

        try {
            await adminApi.addProblem({
                title, category, difficulty, description,
                exampleInput, exampleOutput, tags, timeLimit,
                testCases: [{ input: exampleInput, output: exampleOutput }],
            });
            toast('题目添加成功', 'success');
            renderAdminPanel('problems');
        } catch (err) {
            toast(err.message, 'error');
        }
    };
}

/* ==================== 标签管理 ==================== */
async function renderTagsPanel(root) {
    const tags = await adminApi.tags();
    root.innerHTML = `
        <h2>标签管理</h2>
        <p class="subtitle">管理全局标签。删除标签会同时从所有题目的 meta.json 中移除。</p>
        <div class="admin-list">
            ${tags.length === 0 ? emptyHtml('暂无标签') :
                tags.map(t => `
                    <div class="admin-list-item">
                        <span class="tag-chip">${escapeHtml(t)}</span>
                        <button class="btn btn-danger btn-sm delete-tag" data-tag="${escapeHtml(t)}">删除</button>
                    </div>
                `).join('')}
        </div>
        <hr />
        <h4>添加标签</h4>
        <form id="adminAddTagForm" class="admin-form">
            <div class="form-group"><label>标签名</label><input type="text" id="admNewTag" placeholder="例如：动态规划" required /></div>
            <button type="submit" class="btn btn-success">
                <img src="assets/icons/icon-plus.svg" alt="" class="btn-icon" />
                添加标签
            </button>
        </form>
    `;

    root.querySelectorAll('.delete-tag').forEach(btn => {
        btn.onclick = async () => {
            const tag = btn.dataset.tag;
            if (!await confirmDialog(`确定要删除标签 "${tag}" 吗？`)) return;
            try {
                await adminApi.deleteTag(tag);
                toast('删除成功', 'success');
                renderAdminPanel('tags');
            } catch (err) {
                toast(err.message, 'error');
            }
        };
    });

    root.querySelector('#adminAddTagForm').onsubmit = async (e) => {
        e.preventDefault();
        const tag = root.querySelector('#admNewTag').value.trim();
        if (!tag) return;
        try {
            await adminApi.addTag(tag);
            toast('添加成功', 'success');
            renderAdminPanel('tags');
        } catch (err) {
            toast(err.message, 'error');
        }
    };
}