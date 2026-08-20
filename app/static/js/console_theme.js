/* console_theme.js —— 控制台亮/暗主题切换（前端重构方案 D1/D2）
 * 双轨同步：html[data-theme] 驱动 CSS 变量 token；html[data-bs-theme] 驱动 Bootstrap 5.3 原生暗色。
 * 初值：localStorage > 系统偏好。持久化 key: console-theme。 */
(function () {
  var KEY = 'console-theme';
  function apply(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.setAttribute('data-bs-theme', theme);
  }
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) { /* 隐私模式 */ }
  apply(saved || (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-console-theme-toggle]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        apply(cur);
        try { localStorage.setItem(KEY, cur); } catch (e) { /* 忽略 */ }
        document.dispatchEvent(new CustomEvent('console-theme-changed', { detail: { theme: cur } }));
      });
    });
  });
})();
