import request from '@/config/axios'

// ==================== 待审成果 ====================

/**
 * 提交成果(multipart)。
 * 后端是 `@RequestPart("file")` + `@RequestParam("data")` + `@RequestParam("achievementType")`:
 * file 走文件域,另两个是普通 form 字段,data 是结构化字段的 JSON 字符串。
 * 提交人身份由服务端按登录用户判定,不信任前端传值。
 * @param file        奖状/证书等原始文件
 * @param achievementType award|patent|software|innovation|other
 * @param data        结构化字段的 JSON 字符串
 */
export const submitPending = async (file: File, achievementType: string, data: string) => {
  const form = new FormData()
  form.append('file', file)
  form.append('achievementType', achievementType)
  form.append('data', data)
  return await request.post({ url: '/business/pending-achievements/submit', data: form })
}

/** 获得我的提交分页(学生/教师门户共用;服务端强制按当前登录用户过滤) */
export const getMyPendingPage = async (params: any) => {
  return await request.get({ url: '/business/pending-achievements/my-page', params })
}

/** 撤回我的提交(仅 pending 态可撤) */
export const withdrawPending = async (id: number) => {
  return await request.delete({ url: '/business/pending-achievements/withdraw?id=' + id })
}

/** 获得待审成果时间线(本人/教师/管理员可见) */
export const getPendingTimeline = async (id: number) => {
  return await request.get({ url: '/business/pending-achievements/' + id + '/timeline' })
}

/**
 * 获得 AI 审核建议。
 * 返回 record Suggestion(decision, issuesJson, suggestion, code, message, degraded):
 * decision 为 pass|reject|need-manual,code 为 0 或 4003(Worker 降级)。
 * issuesJson 是 JSON 字符串,需前端自行 parse。
 */
export const getAiSuggest = async (id: number) => {
  return await request.get({ url: '/business/pending-achievements/' + id + '/ai-suggest' })
}

/** 审核(approve 通过并物化 / reject 驳回;服务端仅放行教师/管理员) */
export const reviewPending = async (id: number, data: { action: 'approve' | 'reject'; comment?: string }) => {
  return await request.post({ url: '/business/pending-achievements/' + id + '/review', data })
}

/**
 * 下载待审成果文件。
 * 服务端固定 `Content-Disposition: attachment`,且存储根无静态资源映射,
 * 所以**不能**直接给 `<img src>` 用。要在页面里显示证书图必须:
 *   const blob = await downloadPending(id); const url = URL.createObjectURL(blob)
 * 字节上该文件与物化写入的 certificate_path 指向同一个文件。
 */
export const downloadPending = async (id: number) => {
  return await request.download({ url: '/business/pending-achievements/download?id=' + id })
}

/**
 * 教师待审列表。无 VO,jdbc 直出,驼峰键名即契约:
 * id / achievementType / status / submitterType / submitterId / submitterName / submitTime
 * @param status 可选状态过滤(pending/archived/rejected),不传为全部
 */
export const getTeacherPendingList = async (params?: { status?: string }) => {
  return await request.get({ url: '/business/pending-achievements/teacher-pending-list', params })
}

// ==================== 成果库 ====================

/** 五类成果的类型键(与后端 VaultSpec 白名单一致) */
export const VAULT_TYPES = ['award', 'patent', 'software', 'innovation', 'other'] as const
export type VaultType = (typeof VAULT_TYPES)[number]

/** 获得成果库分页。无 VO,返回 { list, total };行的列集按 type 而异 */
export const getVaultPage = async (type: VaultType | string, params: any) => {
  return await request.get({ url: '/business/vault/' + type, params })
}

/** 编辑成果库行(可改字段按 type 白名单,白名单外会被拒) */
export const updateVaultRow = async (type: VaultType | string, id: number, data: any) => {
  return await request.post({ url: `/business/vault/${type}/${id}/update`, data })
}

/** 删除成果库行(被引用的行会被拒) */
export const deleteVaultRow = async (type: VaultType | string, id: number) => {
  return await request.delete({ url: `/business/vault/${type}/${id}` })
}
