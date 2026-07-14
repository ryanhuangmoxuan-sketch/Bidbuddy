/**
 * BidBuddy — 前端交互逻辑
 * Apple 极简风 · SSE 实时日志 · 多模型切换
 */

const API = '';

// ─── 全局状态 ─────────────────────────────────
let currentConfig = {};
let currentSites = [];
let currentModel = 'deepseek-chat';
let currentModelName = 'DeepSeek Chat';
let currentApiKey = '';
let currentCustomUrl = '';
let allModels = [];

// ─── 初始化 ───────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    refreshStatus();
    loadLogs();
    loadModels();
    loadConfig();

    // 定期刷新
    setInterval(refreshStatus, 4000);
    setInterval(loadLogs, 3000);

    // SSE 实时日志流
    initSSE();
});

// ─── SSE 实时日志 ─────────────────────────────
function initSSE() {
    const es = new EventSource(API + '/api/stream');
    es.onmessage = (e) => {
        const console = document.getElementById('logConsole');
        if (!console) return;

        // 移除空状态
        const empty = console.querySelector('.log-empty');
        if (empty) empty.remove();

        const line = document.createElement('div');
        line.className = 'log-line';
        if (e.data.includes('✅') || e.data.includes('成功')) line.classList.add('success');
        else if (e.data.includes('❌') || e.data.includes('失败')) line.classList.add('error');
        else if (e.data.includes('🤖') || e.data.includes('AI')) line.classList.add('info');
        line.textContent = e.data;
        console.appendChild(line);

        // 保持滚动在底部
        const nearBottom = console.scrollHeight - console.scrollTop - console.clientHeight < 60;
        if (nearBottom) console.scrollTop = console.scrollHeight;

        // 限制DOM节点
        while (console.children.length > 300) {
            console.removeChild(console.firstChild);
        }
    };
    es.onerror = () => { /* 自动重连 */ };
}

// ─── 页面切换 ─────────────────────────────────
function switchPage(name) {
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const page = document.getElementById('page-' + name);
    if (page) page.classList.add('active');

    const nav = document.querySelector(`.nav-item[data-page="${name}"]`);
    if (nav) nav.classList.add('active');

    if (name === 'results') loadResults();
    if (name === 'sites') loadSites();
    if (name === 'settings') loadConfig();
}

// ─── 状态刷新 ─────────────────────────────────
async function refreshStatus() {
    try {
        const res = await fetch(API + '/api/status');
        const data = await res.json();

        // 统计
        document.getElementById('statToday').textContent = data.today_new ?? '—';
        document.getElementById('statRounds').textContent = data.today_rounds ?? '—';
        document.getElementById('statTotal').textContent = data.total_bids ?? '—';

        // 控制按钮
        const btnStart = document.getElementById('btnStart');
        const btnStop = document.getElementById('btnStop');
        if (data.is_running) {
            btnStart.disabled = true;
            btnStop.disabled = false;
        } else {
            btnStart.disabled = false;
            btnStop.disabled = true;
        }

        // 下次执行时间
        const nextLabel = document.getElementById('nextRunLabel');
        if (data.is_running && data.next_run) {
            nextLabel.textContent = '下次: ' + data.next_run;
        } else if (data.is_running) {
            nextLabel.textContent = '执行中...';
        } else {
            nextLabel.textContent = '';
        }

        // 间隔徽标
        document.getElementById('intervalBadge').textContent = '间隔: ' + (data.interval || 20) + '分钟';

        // 进度条
        const progCard = document.getElementById('progressCard');
        if (data.is_crawling && data.progress_total > 0) {
            progCard.style.display = 'block';
            document.getElementById('progressStats').textContent = data.progress_current + '/' + data.progress_total;
            const pct = Math.round((data.progress_current / data.progress_total) * 100);
            document.getElementById('progressFill').style.width = pct + '%';
            document.getElementById('progressSite').textContent = data.progress_site || '准备中...';
        } else if (!data.is_crawling) {
            progCard.style.display = 'none';
        }

        // 侧边栏状态
        const sd = document.getElementById('sidebarStatus');
        const sdt = document.getElementById('sidebarStatusText');
        if (data.is_running) {
            sd.style.background = 'var(--green)';
            sdt.textContent = '监控中';
        } else {
            sd.style.background = 'var(--sidebar-muted)';
            sdt.textContent = '就绪';
        }

        // 结果徽标
        const badge = document.getElementById('resultBadge');
        if (data.today_new > 0) {
            badge.style.display = 'inline';
            badge.textContent = data.today_new;
        } else {
            badge.style.display = 'none';
        }
    } catch (e) {
        console.error('Status error:', e);
    }
}

// ─── 日志加载 ─────────────────────────────────
async function loadLogs() {
    try {
        const res = await fetch(API + '/api/logs?limit=80');
        const data = await res.json();
        const console = document.getElementById('logConsole');
        if (!console) return;

        // 如果SSE已经在填充日志，就不重复渲染
        if (console.children.length > 0 && console.querySelector('.log-line') && !console.querySelector('.log-empty')) {
            return;
        }

        if (data.logs && data.logs.length > 0) {
            const nearBottom = console.scrollHeight - console.scrollTop - console.clientHeight < 60;
            console.innerHTML = data.logs.map(log => {
                let cls = 'log-line';
                if (log.includes('✅') || log.includes('成功')) cls += ' success';
                else if (log.includes('❌') || log.includes('失败')) cls += ' error';
                else if (log.includes('🤖') || log.includes('AI')) cls += ' info';
                return `<div class="${cls}">${escHtml(log)}</div>`;
            }).join('');
            if (nearBottom) console.scrollTop = console.scrollHeight;
        } else {
            console.innerHTML = '<div class="log-empty">等待操作...</div>';
        }
    } catch (e) {
        console.error('Logs error:', e);
    }
}

// ─── 搜索 ─────────────────────────────────────
async function doSearch() {
    const input = document.getElementById('searchInput');
    const query = input.value.trim();
    if (!query) {
        toast('请输入搜索内容', 'error');
        return;
    }

    try {
        const res = await fetch(API + '/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query }),
        });
        const data = await res.json();
        if (data.success) {
            toast(data.message, 'success');
            input.value = '';
            setTimeout(refreshStatus, 500);
        } else {
            toast(data.message || data.detail || '搜索失败', 'error');
        }
    } catch (e) {
        toast('网络错误: ' + e.message, 'error');
    }
}

function fillSearch(text) {
    document.getElementById('searchInput').value = text;
    document.getElementById('searchInput').focus();
}

// ─── 监控控制 ─────────────────────────────────
async function startMonitor() {
    try {
        const res = await fetch(API + '/api/start', { method: 'POST' });
        const data = await res.json();
        toast(data.message, data.success ? 'success' : 'error');
        refreshStatus();
    } catch (e) { toast('操作失败', 'error'); }
}

async function stopMonitor() {
    try {
        const res = await fetch(API + '/api/stop', { method: 'POST' });
        const data = await res.json();
        toast(data.message, data.success ? 'success' : 'info');
        refreshStatus();
    } catch (e) { toast('操作失败', 'error'); }
}

async function runOnce() {
    try {
        const res = await fetch(API + '/api/run-once', { method: 'POST' });
        const data = await res.json();
        toast(data.message, data.success ? 'success' : 'error');
        setTimeout(refreshStatus, 500);
    } catch (e) { toast('操作失败', 'error'); }
}

async function clearLogs() {
    try {
        await fetch(API + '/api/logs', { method: 'DELETE' });
        document.getElementById('logConsole').innerHTML = '<div class="log-empty">日志已清除</div>';
    } catch (e) { /* ignore */ }
}

// ─── 招标结果 ─────────────────────────────────
async function loadResults() {
    try {
        const res = await fetch(API + '/api/results?limit=100');
        const data = await res.json();
        const container = document.getElementById('resultList');
        document.getElementById('resultCount').textContent = '共 ' + (data.total || 0) + ' 条';

        if (data.items && data.items.length > 0) {
            container.innerHTML = data.items.map(item => `
                <div class="result-item">
                    <div class="result-title">
                        <a href="${escHtml(item.url)}" target="_blank" rel="noopener">${escHtml(item.title)}</a>
                    </div>
                    <div class="result-meta">
                        <span>📅 ${escHtml(item.pub_date)}</span>
                        <span>📍 ${escHtml(item.source)}</span>
                    </div>
                </div>
            `).join('');
        } else {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📭</div>
                    <div class="empty-text">暂无招标信息</div>
                    <div class="empty-hint">在控制台输入关键词开始检索</div>
                </div>`;
        }
    } catch (e) {
        console.error('Results error:', e);
    }
}

// ─── 模型选择 ─────────────────────────────────
async function loadModels() {
    try {
        const res = await fetch(API + '/api/models');
        allModels = await res.json();
        renderModelPicker();
    } catch (e) {
        console.error('Models error:', e);
    }
}

function renderModelPicker() {
    const body = document.getElementById('modelPickerBody');
    let html = '';

    allModels.forEach(provider => {
        html += `<div class="picker-provider">
            <div class="picker-provider-name">${provider.icon} ${provider.provider}</div>`;

        provider.models.forEach(model => {
            const selected = currentModel === model.id ? ' selected' : '';
            html += `
            <div class="picker-model-card${selected}" data-model="${model.id}"
                 onclick="selectModel('${model.id}', '${model.name}', '${model.provider === '自定义' ? '__custom__' : ''}')">
                <div class="picker-model-icon">${model.icon}</div>
                <div class="picker-model-info">
                    <div class="picker-model-name">${model.name}</div>
                    <div class="picker-model-desc">${model.description}</div>
                </div>
                <div class="picker-model-check">✓</div>
            </div>`;
        });

        html += '</div>';
    });

    body.innerHTML = html;
}

function selectModel(id, name, isCustom) {
    currentModel = id;
    currentModelName = name;

    // 更新侧边栏
    document.getElementById('currentModelName').textContent = name;

    // 更新选中状态
    document.querySelectorAll('.picker-model-card').forEach(c => {
        c.classList.toggle('selected', c.dataset.model === id);
    });

    // 更新设置页
    const display = document.getElementById('aiModelDisplay');
    if (display) display.textContent = name;

    // 显示/隐藏自定义URL
    const customGroup = document.getElementById('customUrlGroup');
    if (customGroup) customGroup.style.display = isCustom ? 'block' : 'none';

    toast('已切换至 ' + name, 'info');
}

function toggleModelPicker() {
    const picker = document.getElementById('modelPicker');
    if (picker.style.display === 'none') {
        picker.style.display = 'block';
        renderModelPicker();
    } else {
        picker.style.display = 'none';
    }
}

// 点击外部关闭
document.addEventListener('click', (e) => {
    const picker = document.getElementById('modelPicker');
    const selector = document.getElementById('modelSelector');
    if (picker && selector && picker.style.display !== 'none') {
        if (!picker.contains(e.target) && !selector.contains(e.target)) {
            picker.style.display = 'none';
        }
    }
});

// ─── 网站管理 ─────────────────────────────────
async function loadSites() {
    try {
        const res = await fetch(API + '/api/sites');
        currentSites = await res.json();
        renderSites();
    } catch (e) {
        console.error('Sites error:', e);
    }
}

function renderSites() {
    const grid = document.getElementById('sitesGrid');
    if (!currentSites.length) {
        grid.innerHTML = '<div class="empty-state"><div class="empty-text">加载失败</div></div>';
        return;
    }

    grid.innerHTML = currentSites.map(site => `
        <div class="site-chip${site.enabled ? ' enabled' : ''}" onclick="toggleSite('${site.key}', this)">
            <div class="site-check">${site.enabled ? '✓' : ''}</div>
            <span>${escHtml(site.name)}</span>
        </div>
    `).join('');
}

function toggleSite(key, el) {
    const site = currentSites.find(s => s.key === key);
    if (site) {
        site.enabled = !site.enabled;
        el.classList.toggle('enabled', site.enabled);
        el.querySelector('.site-check').textContent = site.enabled ? '✓' : '';
    }
}

function selectAllSites() {
    currentSites.forEach(s => s.enabled = true);
    renderSites();
}

function deselectAllSites() {
    currentSites.forEach(s => s.enabled = false);
    renderSites();
}

async function saveSites() {
    const enabled = currentSites.filter(s => s.enabled).map(s => s.key);
    try {
        await fetch(API + '/api/sites', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(enabled),
        });
        toast('网站配置已保存', 'success');
    } catch (e) {
        toast('保存失败', 'error');
    }
}

// ─── 设置页 ───────────────────────────────────
async function loadConfig() {
    try {
        const res = await fetch(API + '/api/config');
        currentConfig = await res.json();

        document.getElementById('cfgKeywords').value = currentConfig.keywords || '';
        document.getElementById('cfgExclude').value = currentConfig.exclude || '';
        document.getElementById('cfgMustContain').value = currentConfig.must_contain || '';
        document.getElementById('cfgInterval').value = currentConfig.interval || 20;
        document.getElementById('cfgSelenium').checked = currentConfig.use_selenium || false;

        // AI 配置
        const aiEnabled = currentConfig.ai_enabled || false;
        document.getElementById('cfgAiEnabled').checked = aiEnabled;
        document.getElementById('aiConfigSection').style.display = aiEnabled ? 'block' : 'none';
        document.getElementById('cfgAiKey').value = currentConfig.ai_key || '';
        document.getElementById('cfgAiCustomUrl').value = currentConfig.ai_custom_url || '';

        const aiModel = currentConfig.ai_model || 'deepseek-chat';
        currentModel = aiModel;

        // 更新模型显示
        const display = document.getElementById('aiModelDisplay');
        if (display) {
            const info = allModels.flatMap(p => p.models).find(m => m.id === aiModel);
            display.textContent = info ? info.name : aiModel;
        }

        // 更新模型选择器
        const modelNameEl = document.getElementById('currentModelName');
        if (modelNameEl && currentModel !== '__custom__') {
            const info = allModels.flatMap(p => p.models).find(m => m.id === currentModel);
            if (info) modelNameEl.textContent = info.name;
        }

        // 自定义URL显示
        const customGroup = document.getElementById('customUrlGroup');
        if (customGroup) customGroup.style.display = currentModel === '__custom__' ? 'block' : 'none';
    } catch (e) {
        console.error('Config error:', e);
    }
}

async function saveSettings() {
    const config = {
        keywords: document.getElementById('cfgKeywords').value,
        exclude: document.getElementById('cfgExclude').value,
        must_contain: document.getElementById('cfgMustContain').value,
        interval: parseInt(document.getElementById('cfgInterval').value) || 20,
        use_selenium: document.getElementById('cfgSelenium').checked,
    };

    try {
        await fetch(API + '/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        toast('搜索配置已保存', 'success');
    } catch (e) {
        toast('保存失败', 'error');
    }
}

function toggleAiConfig() {
    const enabled = document.getElementById('cfgAiEnabled').checked;
    document.getElementById('aiConfigSection').style.display = enabled ? 'block' : 'none';
}

async function saveAiConfig() {
    const apiKey = document.getElementById('cfgAiKey').value;

    const config = {
        ai_enabled: document.getElementById('cfgAiEnabled').checked,
        ai_model: currentModel,
        ai_key: apiKey,
        ai_custom_url: currentModel === '__custom__' ? document.getElementById('cfgAiCustomUrl').value : '',
    };

    try {
        await fetch(API + '/api/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });
        toast('AI配置已保存', 'success');
    } catch (e) {
        toast('保存失败', 'error');
    }
}

async function testAiConnection() {
    const apiKey = document.getElementById('cfgAiKey').value;
    if (!apiKey) {
        toast('请先输入 API Key', 'error');
        return;
    }

    toast('正在测试连接...', 'info');

    try {
        const res = await fetch(API + '/api/models/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                model: currentModel,
                api_key: apiKey,
                custom_url: currentModel === '__custom__' ? document.getElementById('cfgAiCustomUrl').value : '',
            }),
        });
        const data = await res.json();
        if (data.success) {
            toast('✅ ' + data.message, 'success');
        } else {
            toast('❌ ' + data.message, 'error');
        }
    } catch (e) {
        toast('测试失败: ' + e.message, 'error');
    }
}

async function clearHistory() {
    if (!confirm('确定要清空所有历史招标数据吗？此操作不可恢复。')) return;
    try {
        await fetch(API + '/api/history', { method: 'DELETE' });
        toast('历史数据已清空', 'info');
        refreshStatus();
        if (document.getElementById('page-results').classList.contains('active')) {
            loadResults();
        }
    } catch (e) {
        toast('操作失败', 'error');
    }
}

// ─── 工具函数 ─────────────────────────────────
function toast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.textContent = message;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3000);
}

function escHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}
