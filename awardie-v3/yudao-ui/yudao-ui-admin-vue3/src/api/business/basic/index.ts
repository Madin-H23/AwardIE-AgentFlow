import request from '@/config/axios'

// ==================== 竞赛 ====================

/** 获得竞赛分页 */
export const getCompetitionPage = async (params: any) => {
  return await request.get({ url: '/business/competitions/page', params })
}

/** 获得竞赛详情 */
export const getCompetition = async (id: number) => {
  return await request.get({ url: '/business/competitions/get?id=' + id })
}

/** 创建竞赛 */
export const createCompetition = async (data: any) => {
  return await request.post({ url: '/business/competitions/create', data })
}

/** 更新竞赛(体含 id,不单独传) */
export const updateCompetition = async (data: any) => {
  return await request.put({ url: '/business/competitions/update', data })
}

/** 删除竞赛 */
export const deleteCompetition = async (id: number) => {
  return await request.delete({ url: '/business/competitions/delete?id=' + id })
}

/** 批量删除竞赛 */
export const deleteCompetitionList = async (ids: number[]) => {
  return await request.delete({ url: '/business/competitions/delete-list?ids=' + ids.join(',') })
}

/** 导出竞赛 Excel(.xls) */
export const exportCompetitionExcel = async (params?: any) => {
  return await request.download({ url: '/business/competitions/export-excel', params })
}

// ==================== 实验室 ====================

/** 获得实验室分页 */
export const getLaboratoryPage = async (params: any) => {
  return await request.get({ url: '/business/laboratories/page', params })
}

/** 获得实验室详情 */
export const getLaboratory = async (id: number) => {
  return await request.get({ url: '/business/laboratories/get?id=' + id })
}

/** 创建实验室 */
export const createLaboratory = async (data: any) => {
  return await request.post({ url: '/business/laboratories/create', data })
}

/** 更新实验室(体含 id,不单独传) */
export const updateLaboratory = async (data: any) => {
  return await request.put({ url: '/business/laboratories/update', data })
}

/** 删除实验室 */
export const deleteLaboratory = async (id: number) => {
  return await request.delete({ url: '/business/laboratories/delete?id=' + id })
}

/** 批量删除实验室 */
export const deleteLaboratoryList = async (ids: number[]) => {
  return await request.delete({ url: '/business/laboratories/delete-list?ids=' + ids.join(',') })
}

/** 导出实验室 Excel(.xls) */
export const exportLaboratoryExcel = async (params?: any) => {
  return await request.download({ url: '/business/laboratories/export-excel', params })
}

/**
 * 实验室详情聚合。无 VO,Map 的键名即契约:
 * instructors / students / downloadCount / awardCount
 */
export const getLaboratoryDetail = async (id: number) => {
  return await request.get({ url: '/business/laboratories/detail?id=' + id })
}

/** 实验室附件列表。无 VO,行是 awardie_laboratory_downloads 的原始列 */
export const getLaboratoryDownloads = async (id: number) => {
  return await request.get({ url: '/business/laboratories/downloads?id=' + id })
}
