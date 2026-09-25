import request from '@/config/axios'

// ==================== 证书模板 ====================

/** 获得证书模板分页 */
export const getTemplatePage = async (params: any) => {
  return await request.get({ url: '/business/templates/page', params })
}

/** 获得证书模板详情 */
export const getTemplate = async (id: number) => {
  return await request.get({ url: '/business/templates/get?id=' + id })
}

/** 创建证书模板(multipart:文件 + data) */
export const createTemplate = async (data: FormData) => {
  return await request.post({ url: '/business/templates/create', data })
}

/** 更新证书模板 */
export const updateTemplate = async (id: number, data: any) => {
  return await request.put({ url: '/business/templates/update?id=' + id, data })
}

/** 删除证书模板 */
export const deleteTemplate = async (id: number) => {
  return await request.delete({ url: '/business/templates/delete?id=' + id })
}

/** 回显模板样本图(返回二进制,需用 blob 方式取) */
export const getTemplateImageUrl = (id: number) => {
  return import.meta.env.VITE_BASE_URL + import.meta.env.VITE_API_URL + '/business/templates/image?id=' + id
}

/** 模板试测(AI 抽取) */
export const testTemplate = async (id: number) => {
  return await request.post({ url: '/business/templates/test?id=' + id })
}

/** 创建前 AI 抽取 */
export const extractForCreate = async (data: FormData) => {
  return await request.post({ url: '/business/templates/extract-for-create', data })
}

/** 生成 prompt */
export const generatePrompt = async (params: any) => {
  return await request.post({ url: '/business/templates/generate-prompt', params })
}

// ==================== 大创 ====================

/** 获得大创分页 */
export const getInnovationPage = async (params: any) => {
  return await request.get({ url: '/business/innovations/page', params })
}

/** 获得大创详情 */
export const getInnovation = async (id: number) => {
  return await request.get({ url: '/business/innovations/get?id=' + id })
}

/** 更新大创 */
export const updateInnovation = async (id: number, data: any) => {
  return await request.put({ url: '/business/innovations/update?id=' + id, data })
}

/** 大创 xlsx 导入预览 */
export const previewInnovationImport = async (data: FormData) => {
  return await request.post({ url: '/business/innovations/import/preview', data })
}

/** 大创 xlsx 导入确认(凭 token) */
export const confirmInnovationImport = async (token: string) => {
  return await request.post({ url: '/business/innovations/import/confirm', params: { token } })
}

/** 大创状态批量校准 */
export const calibrateInnovationStatus = async () => {
  return await request.post({ url: '/business/innovations/calibrate-status' })
}

// ==================== 统计分析 ====================

/** 获得统计总览 */
export const getStatsOverview = async () => {
  return await request.get({ url: '/business/stats/overview' })
}

/** 获得竞赛战果 Top12 */
export const getStatsByCompetition = async () => {
  return await request.get({ url: '/business/stats/by-competition' })
}

// ==================== 数据导出 ====================

/** 导出竞赛年度汇总 CSV */
export const exportCompetitionSummaryCsv = () => {
  return request.download({ url: '/business/export/competition-summary.csv' })
}

/** 导出竞赛年度汇总 XLSX */
export const exportCompetitionSummaryXlsx = () => {
  return request.download({ url: '/business/export/competition-summary.xlsx' })
}

/** 导出学生获奖明细 CSV */
export const exportStudentAffairsCsv = () => {
  return request.download({ url: '/business/export/student-affairs.csv' })
}

/** 导出学生获奖明细 XLSX */
export const exportStudentAffairsXlsx = () => {
  return request.download({ url: '/business/export/student-affairs.xlsx' })
}

// ==================== 业务日志 ====================

/** 获得业务审计日志分页 */
export const getAuditLogPage = async (params: any) => {
  return await request.get({ url: '/business/logs/audit', params })
}
