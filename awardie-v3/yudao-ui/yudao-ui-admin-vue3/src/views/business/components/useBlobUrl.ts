import { onBeforeUnmount, ref, shallowRef } from 'vue'

/**
 * 受鉴权保护的图片回显。
 *
 * 为什么不能直接 `<img :src="url">`:
 * 1. 芋道的鉴权走 `Authorization: Bearer <token>` 头,`<img src>` 不带请求头 → 必然 401;
 * 2. 存储根(files/v3)没有任何静态资源映射,`filePath` 是磁盘相对路径不是 URL 片段;
 * 3. 待审成果的 `/download` 端点还固定 `Content-Disposition: attachment`。
 *
 * 所以唯一可行路径是:request.download 取 Blob → createObjectURL → 渲染,
 * 并在组件卸载时 revoke,否则 objectURL 会一直占着 Blob 内存不释放。
 *
 * 参数在 load() 时传,不在创建时固定——详情抽屉每行换一条记录,
 * 固定参数就得为每行重建一个实例。
 *
 * @param fetcher 返回 Blob 的函数,如 (id) => downloadPending(id)
 */
export const useBlobUrl = <T extends unknown[]>(fetcher: (...args: T) => Promise<Blob>) => {
  const url = shallowRef<string>('')
  const loading = ref(false)
  const failed = ref(false)

  // 记录当前仍有效的 objectURL,竞态时只 revoke 最后一次的结果
  let current: string | undefined

  const revoke = () => {
    if (current) {
      URL.revokeObjectURL(current)
      current = undefined
    }
    url.value = ''
  }

  const load = async (...args: T) => {
    loading.value = true
    failed.value = false
    try {
      const blob = await fetcher(...args)
      revoke()
      current = URL.createObjectURL(blob)
      url.value = current
    } catch {
      // 404/403/500 都归到这里:图显示不出来,但不能让整页崩
      failed.value = true
      revoke()
    } finally {
      loading.value = false
    }
  }

  onBeforeUnmount(revoke)

  return { url, loading, failed, load, revoke }
}
