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

/** 更新竞赛 */
export const updateCompetition = async (data: any) => {
  return await request.put({ url: '/business/competitions/update', data })
}

/** 删除竞赛 */
export const deleteCompetition = async (id: number) => {
  return await request.delete({ url: '/business/competitions/delete?id=' + id })
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

/** 更新实验室 */
export const updateLaboratory = async (data: any) => {
  return await request.put({ url: '/business/laboratories/update', data })
}

/** 删除实验室 */
export const deleteLaboratory = async (id: number) => {
  return await request.delete({ url: '/business/laboratories/delete?id=' + id })
}
