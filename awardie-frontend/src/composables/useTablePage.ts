import { reactive, ref } from 'vue'
import { apiJson } from './useCsrf'

export interface TablePageOptions<T> {
  /** 列表端点(GET),响应须为 ApiResponse<Page|PageView>(content/totalElements) */
  api: string
  /** 每页条数,默认 20 */
  size?: number
  /** 筛选字段初始值(空串=不过滤,拼参数时剔除) */
  filters?: Record<string, string | number | null>
  /** 从响应 data 提取列表与总数;默认 Page/PageView 结构 */
  extract?: (data: unknown) => { content: T[]; total: number }
}

/**
 * #27 列表标准化:分页(1 基展示/0 基请求)+筛选+loading 统一态。
 * 用法:const tp = useTablePage<Row>({ api: '/api/v2/...', filters: { keyword: '' } })
 * 模板:el-table v-loading="tp.loading" + el-pagination @current-change="tp.go"
 */
export function useTablePage<T>(opts: TablePageOptions<T>) {
  const rows = ref<T[]>([]) as { value: T[] }
  const total = ref(0)
  const page = ref(1)
  const size = ref(opts.size ?? 20)
  const loading = ref(false)
  const filters = reactive<Record<string, string | number | null>>(
    Object.fromEntries(Object.entries(opts.filters ?? {}).map(([k, v]) => [k, v])),
  )

  async function load() {
    loading.value = true
    try {
      const qs = new URLSearchParams({ page: String(page.value - 1), size: String(size.value) })
      for (const [k, v] of Object.entries(filters)) {
        if (v !== null && v !== undefined && String(v).trim() !== '') qs.set(k, String(v))
      }
      const body = await apiJson('GET', `${opts.api}?${qs}`)
      if (body.code === 0) {
        const extracted = opts.extract
          ? opts.extract(body.data)
          : { content: body.data.content as T[], total: body.data.totalElements as number }
        rows.value = extracted.content
        total.value = extracted.total
      }
    } finally {
      loading.value = false
    }
  }

  /** 翻页(el-pagination current-change 直传 1 基页码) */
  function go(p: number) {
    page.value = p
    return load()
  }

  /** 应用筛选回第 1 页 */
  function search() {
    page.value = 1
    return load()
  }

  /** 重置筛选与页码 */
  function reset() {
    for (const [k, v] of Object.entries(opts.filters ?? {})) filters[k] = v
    page.value = 1
    return load()
  }

  return { rows, total, page, size, loading, filters, load, go, search, reset }
}
