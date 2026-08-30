// CSRF(#16):Cookie 方案——读 XSRF-TOKEN cookie 回传 X-XSRF-TOKEN 头。
// token 全局有效(非一次性);GET /api/v2/auth/csrf 显式签发。
export function xsrfToken(): string {
  const m = document.cookie.match(/(?:^|; )XSRF-TOKEN=([^;]*)/)
  return m ? decodeURIComponent(m[1]) : ''
}

export async function ensureCsrf() {
  if (xsrfToken()) return
  await fetch('/api/v2/auth/csrf', { credentials: 'include' })
}

/** JSON POST/PUT/DELETE 通用封装:自动带 CSRF 与会话。 */
export async function apiJson(method: string, url: string, body?: unknown) {
  await ensureCsrf()
  const resp = await fetch(url, {
    method,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-XSRF-TOKEN': xsrfToken(),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  return resp.json()
}
