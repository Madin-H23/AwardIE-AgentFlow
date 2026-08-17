/* CSRF 全局防护前端层 (P1-1 / 设计文档安全章 2.1)
 * 三件事，一处覆盖全站：
 * 1) 同源 fetch 写请求自动注入 X-CSRF-Token 头
 * 2) XMLHttpRequest 写请求自动注入头（4 处存量 ajax）
 * 3) 所有 method=POST 的原生表单动态补 hidden csrf_token（40 模板免逐一改造）
 * token 来源：<meta name="csrf-token">（两套基础模板注入，CSRFProtect 提供 csrf_token()）
 */
(function () {
    'use strict';
    var token = null;
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta) { token = meta.getAttribute('content'); }
    if (!token) { return; }

    function isWriteMethod(m) {
        return ['POST', 'PUT', 'PATCH', 'DELETE'].indexOf((m || 'GET').toUpperCase()) >= 0;
    }
    function sameOrigin(url) {
        try {
            var u = new URL(url, window.location.href);
            return u.origin === window.location.origin;
        } catch (e) { return true; }  // 相对地址
    }

    /* 1) fetch patch */
    var _fetch = window.fetch;
    if (_fetch) {
        window.fetch = function (input, init) {
            try {
                var url = (typeof input === 'string') ? input : (input && input.url) || '';
                var method = (init && init.method) || (input && input.method) || 'GET';
                if (token && isWriteMethod(method) && sameOrigin(url)) {
                    init = init || {};
                    if (input instanceof Request) {  // Request 对象形态：重建
                        init = Object.assign({ method: input.method, body: input.body }, init);
                        input = url;
                    }
                    init.headers = init.headers || {};
                    if (typeof init.headers.set === 'function') { init.headers.set('X-CSRF-Token', token); }
                    else { init.headers['X-CSRF-Token'] = token; }
                }
            } catch (e) { /* 防御：不因注入失败阻断原请求 */ }
            return _fetch.call(this, input, init);
        };
    }

    /* 2) XHR patch */
    var _open = XMLHttpRequest.prototype.open;
    var _setRH = XMLHttpRequest.prototype.setRequestHeader;
    XMLHttpRequest.prototype.open = function (method, url) {
        this._csrfWrite = isWriteMethod(method) && sameOrigin(url);
        return _open.apply(this, arguments);
    };
    XMLHttpRequest.prototype.setRequestHeader = function (name, value) {
        if (this._csrfWrite && name === 'X-CSRF-Token') { this._csrfSent = true; }
        return _setRH.apply(this, arguments);
    };
    var _send = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function () {
        if (this._csrfWrite && !this._csrfSent) {
            try { _setRH.call(this, 'X-CSRF-Token', token); } catch (e) { }
        }
        return _send.apply(this, arguments);
    };

    /* 3) POST 表单动态补 hidden token */
    function injectForms() {
        if (!document.querySelectorAll) { return; }
        document.querySelectorAll('form').forEach(function (form) {
            var m = (form.getAttribute('method') || 'GET').toUpperCase();
            if (m !== 'POST' || form.querySelector('input[name="csrf_token"]')) { return; }
            var input = document.createElement('input');
            input.type = 'hidden';
            input.name = 'csrf_token';
            input.value = token;
            form.appendChild(input);
        });
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectForms);
    } else { injectForms(); }
})();
