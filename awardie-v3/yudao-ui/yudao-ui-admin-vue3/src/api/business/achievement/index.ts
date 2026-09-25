import request from '@/config/axios'

// ==================== 待审成果 ====================

/** 获得我的提交分页(学生/教师用) */
export const getMyPendingPage = async (params: any) => {
  return await request.get({ url: '/business/pending-achievements/my-page', params })
}

/** 获得待审成果时间线 */
export const getPendingTimeline = async (id: number) => {
  return await request.get({ url: '/business/pending-achievements/' + id + '/timeline' })
}

/** 获得 AI 审核建议 */
export const getAiSuggest = async (id: number) => {
  return await request.get({ url: '/business/pending-achievements/' + id + '/ai-suggest' })
}

/** 审核(通过/驳回) */
export const reviewPending = async (id: number, data: any) => {
  return await request.post({ url: '/business/pending-achievements/' + id + '/review', data })
}

/** 下载待审成果文件(attachment) */
export const downloadPending = async (id: number) => {
  return request.download({ url: '/business/pending-achievements/download?id=' + id })
}

// ==================== 成果库 ====================

/** 获得成果库分页(type: award/patent/software/innovation/other) */
export const getVaultPage = async (type: string, params: any) => {
  return await request.get({ url: '/business/vault/' + type, params })
}

/** 编辑成果库行 */
export const updateVaultRow = async (type: string, id: number, data: any) => {
  return await request.post({ url: `/business/vault/${type}/${id}/update`, data })
}

/** 删除成果库行 */
export const deleteVaultRow = async (type: string, id: number) => {
  return await request.delete({ url: `/business/vault/${type}/${id}` })
}
