/* console_boot.js —— 三基类共享启动兜底
   ①storage 安全：禁 storage 上下文（WebView/严格隐私）降级为内存，绝不抛异常；
   ②全局 error/unhandledrejection 捕获 → 右上角可见错误条 + console.error（含 stack），
     白屏不再静默，便于定位（排障清单 P16）。 */
(function () {
    'use strict';
    // 1) storage 安全包装
    var mem = {};
    try {
        window.__safeLocal = {
            get: function (k) { try { return localStorage.getItem(k); } catch (e) { return Object.prototype.hasOwnProperty.call(mem, k) ? mem[k] : null; } },
            set: function (k, v) { try { localStorage.setItem(k, v); } catch (e) { mem[k] = v; } },
            remove: function (k) { try { localStorage.removeItem(k); } catch (e) { delete mem[k]; } }
        };
    } catch (e) { /* 连检测都不行则用空实现 */ window.__safeLocal = { get: function () { return null; }, set: function () {}, remove: function () {} }; }

    // 2) 错误浮层（无则动态创建，保证三个基类都可见）
    function show(msg, warn) {
        var el = document.getElementById('bootError');
        if (!el) {
            el = document.createElement('div');
            el.id = 'bootError';
            el.style.cssText = 'position:fixed;top:64px;right:16px;z-index:2100;max-width:340px;' +
                'background:#fee2e2;color:#7f1d1d;border:1px solid #fca5a5;border-radius:8px;' +
                'padding:10px 14px;font-size:.82rem;box-shadow:0 8px 24px rgba(0,0,0,.12);line-height:1.5;display:none';
            document.body.appendChild(el);
        }
        el.style.background = warn ? '#fef3c7' : '#fee2e2';
        el.style.color = warn ? '#78350f' : '#7f1d1d';
        el.innerHTML = '⚠ ' + String(msg).replace(/</g, '&lt;');
        el.style.display = 'block';
    }

    // 3) 全局异常捕获
    window.addEventListener('unhandledrejection', function (ev) {
        var r = (ev && ev.reason) || {};
        var d = r.stack || r.message || String(r || 'unknown');
        console.error('boot-unhandledrejection:', d);
        show('异步异常: ' + String(d).slice(0, 200));
    });
    window.addEventListener('error', function (ev) {
        var m = (ev && ev.message) || '未知';
        console.error('boot-error:', (ev && ev.error && ev.error.stack) || m);
        show('页面脚本异常: ' + m);
    });
    setTimeout(function () {
        // 4s 后：仅当 body 几乎无可见内容（真白屏）才提示未渲染；
        // 旧体系页/普通页即使无 console-shell 也有正文，不误报。
        var hasText = (document.body && document.body.innerText && document.body.innerText.trim().length > 20);
        var hasShell = !!document.querySelector('.console-shell, .portal-shell, #app, nav, main, .container');
        if (!hasText && !hasShell) {
            show('页面内容未能渲染（详见控制台）。', true);
        }
    }, 4000);
})();
