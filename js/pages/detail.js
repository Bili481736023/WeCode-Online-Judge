import { problemApi, submissionApi } from '../api.js';
import { store } from '../store.js';
import { escapeHtml, difficultyClass } from '../utils.js';
import { loadingHtml, emptyHtml, toast } from '../ui.js';
import { DEFAULT_CODE } from '../config.js';

export async function renderDetail(id) {
    const container = document.getElementById('detailContainer');
    container.innerHTML = loadingHtml('加载题目中...');

    try {
        if (!store.problems.length) {
            store.problems = await problemApi.list();
        }
        if (store.isLoggedIn() && !store.submissions.length) {
            try { store.submissions = await submissionApi.list(); } catch {}
        }
    } catch (err) {
        container.innerHTML = emptyHtml('加载失败', err.message);
        return;
    }

    const problem = store.problems.find(p => String(p.id) === String(id));
    if (!problem) {
        container.innerHTML = emptyHtml('题目不存在', '请返回题库重新选择');
        return;
    }

    const prevSubs = store.submissions.filter(s => String(s.problemId) === String(problem.id));
    const lastSub = prevSubs.length ? prevSubs[prevSubs.length - 1] : null;

    const defaultLang = lastSub ? lastSub.language : 'cpp';
    const defaultCode = lastSub ? lastSub.code : DEFAULT_CODE[defaultLang];

    container.innerHTML = `
        <div class="back-link" id="detailBack">← 返回题库</div>
        <div class="detail-header">
            <h2>${escapeHtml(problem.title)}</h2>
            <span class="difficulty ${difficultyClass(problem.difficulty)}">${escapeHtml(problem.difficulty || '')}</span>
        </div>
        <div class="detail-body">
            <div class="desc-section">
                <p>${escapeHtml(problem.description || '')}</p>
                <h4>示例输入</h4>
                <div class="example-box">${escapeHtml(problem.exampleInput || '无')}</div>
                <h4>示例输出</h4>
                <div class="example-box">${escapeHtml(problem.exampleOutput || '无')}</div>
                <h4>分类</h4>
                <p>${escapeHtml(problem.category || '未分类')}</p>
                ${problem.tags && problem.tags.length
                    ? `<h4>标签</h4><p>${problem.tags.map(escapeHtml).join('、')}</p>` : ''}
            </div>
            <div class="code-section">
                <div class="form-group">
                    <label>语言</label>
                    <select id="codeLanguage">
                        <option value="cpp" ${defaultLang === 'cpp' ? 'selected' : ''}>C++</option>
                        <option value="python" ${defaultLang === 'python' ? 'selected' : ''}>Python</option>
                    </select>
                </div>
                <textarea id="codeEditor" spellcheck="false"></textarea>
                <div class="action-row">
                    <button class="btn btn-success" id="submitCode">
                        <img src="assets/icons/icon-submit.svg" alt="" class="btn-icon" />
                        提交判题
                    </button>
                    <button class="btn btn-outline" id="resetCode">
                        <img src="assets/icons/icon-reset.svg" alt="" class="btn-icon" />
                        重置
                    </button>
                </div>
                <div id="submitResult" class="submit-result"></div>
            </div>
        </div>
    `;

    const editor = document.getElementById('codeEditor');
    editor.value = defaultCode;

        // Tab 键缩进：支持单行插入、多行整体缩进、Shift+Tab 取消缩进
    editor.addEventListener('keydown', function (e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;

            if (start !== end) {
                // 如果有选中的多行代码
                const text = this.value;
                const selectedText = text.substring(start, end);
                let newText = '';

                if (!e.shiftKey) {
                    // 按 Tab：整体向右缩进 4 个空格
                    newText = selectedText.split('\n').map(line => '    ' + line).join('\n');
                } else {
                    // 按 Shift + Tab：整体向左减少 4 个空格
                    newText = selectedText.split('\n').map(line => {
                        if (line.startsWith('    ')) return line.substring(4);
                        if (line.startsWith('\t')) return line.substring(1);
                        return line;
                    }).join('\n');
                }
                // 替换选中的文本，并保持选中状态
                this.setRangeText(newText, start, end, 'select');
            } else {
                // 没有选中文本时，直接插入 4 个空格，使用 execCommand 可以保留 Ctrl+Z 撤销历史
                document.execCommand('insertText', false, '    ');
            }
        }
    });

    document.getElementById('codeLanguage').onchange = (e) => {
        editor.value = DEFAULT_CODE[e.target.value] || '';
    };
    document.getElementById('detailBack').onclick = () => { location.hash = '#/problems'; };
    document.getElementById('resetCode').onclick = () => {
        editor.value = DEFAULT_CODE[document.getElementById('codeLanguage').value] || '';
        const r = document.getElementById('submitResult');
        r.className = 'submit-result';
        r.textContent = '';
    };
    document.getElementById('submitCode').onclick = () => handleSubmit(problem);
}

async function handleSubmit(problem) {
    if (!store.isLoggedIn()) return toast('请先登录', 'error');

    const code = document.getElementById('codeEditor').value.trim();
    if (!code) return toast('请先写代码', 'error');

    const language = document.getElementById('codeLanguage').value;
    const resultEl = document.getElementById('submitResult');
    const btn = document.getElementById('submitCode');

    btn.disabled = true;
    btn.innerHTML = '<img src="assets/icons/icon-pending.svg" alt="" class="btn-icon" /> 判题中...';
    resultEl.className = 'submit-result show';
    resultEl.textContent = '正在提交并判题，请稍候...';

    try {
        const res = await problemApi.submit({
            code,
            language,
            problemId: problem.id,
            problemTitle: problem.title,
            input: problem.exampleInput || '',
            expected: problem.exampleOutput || '',
        });

        const status = res.status || 'error';
        const accepted = status === 'Accepted';
        resultEl.className = `submit-result show ${accepted ? 'accepted' : 'wrong'}`;
        let text = accepted ? `通过（${status}）` : `未通过（${status}）`;
        if (res.output) text += `\n输出: ${res.output}`;
        if (res.detail) text += `\n详情: ${res.detail}`;
        if (res.message) text += `\n消息: ${res.message}`;
        resultEl.textContent = text;
        toast(accepted ? '通过' : '未通过', accepted ? 'success' : 'error');
    } catch (err) {
        resultEl.className = 'submit-result show wrong';
        resultEl.textContent = `请求失败：${err.message}`;
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<img src="assets/icons/icon-submit.svg" alt="" class="btn-icon" /> 提交判题';
    }
}