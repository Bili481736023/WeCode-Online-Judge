export function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

export function formatTime(iso) {
    if (!iso) return '--';
    const d = new Date(iso);
    if (isNaN(d)) return '--';
    return d.toLocaleString('zh-CN', { hour12: false });
}

export const DIFFICULTY_COLOR = {
    '入门': 'diff-red',
    '普及-': 'diff-orange',
    '普及': 'diff-yellow',
    '普及+/提高-': 'diff-green',
    '提高': 'diff-cyan',
    '提高+/省选-': 'diff-blue',
    '省选/NOI-': 'diff-purple',
    'NOI/NOI+/CTS': 'diff-black',
};

export function difficultyClass(diff) {
    return DIFFICULTY_COLOR[diff] || 'diff-green';
}