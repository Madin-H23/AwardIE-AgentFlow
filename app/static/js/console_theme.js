/* console_theme.js —— 控制台亮/暗主题切换（前端重构方案 D1/D2）
 * 双轨同步：html[data-theme] 驱动 CSS 变量 token；html[data-bs-theme] 驱动 Bootstrap 5.3 原生暗色。
 * 初值：localStorage > 系统偏好。持久化 key: console-theme。 */
(function () {
  var KEY = 'console-theme';
  function syncToggle(theme) {
    var dark = theme === 'dark';
    document.querySelectorAll('[data-console-theme-toggle]').forEach(function (btn) {
      btn.setAttribute('aria-label', dark ? '切换为浅色模式' : '切换为深色模式');
      btn.setAttribute('title', dark ? '切换为浅色模式' : '切换为深色模式');
      btn.setAttribute('aria-pressed', dark ? 'true' : 'false');
      var moon = btn.querySelector('.theme-icon-moon');
      var sun = btn.querySelector('.theme-icon-sun');
      if (moon) moon.style.display = dark ? 'none' : 'block';
      if (sun) sun.style.display = dark ? 'block' : 'none';
    });
  }
  function apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-bs-theme', theme);
    syncToggle(theme);
  }
  var saved = null;
  saved = window.__safeLocal ? __safeLocal.get(KEY) : null;
  try { if (saved === null) saved = localStorage.getItem(KEY); } catch (e) { /* 禁止 storage 时已内存兜底 */ }
  apply(saved || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-console-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        apply(cur);
        if (window.__safeLocal) __safeLocal.set(KEY, cur);
        try { localStorage.setItem(KEY, cur); } catch (e) { /* 忽略 */ }
        document.dispatchEvent(new CustomEvent('console-theme-changed', { detail: { theme: cur } }));
      });
    });

    // 侧边栏分组折叠（百度云风格：分组标题点击展开/收起；状态不入存储，保持简单）
    document.querySelectorAll('.console-sidebar .sb-group-title').forEach(function (title) {
      title.addEventListener('click', function () {
        title.closest('.sb-group').classList.toggle('collapsed');
      });
    });

    // 双图标初始态（内联 style 的 sun 默认隐藏，但首帧保险）
    syncToggle(document.documentElement.getAttribute('data-theme') || 'light');
  });
})();
