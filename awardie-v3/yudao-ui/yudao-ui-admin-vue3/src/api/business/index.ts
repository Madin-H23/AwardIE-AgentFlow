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

/**
 * 创建证书模板。
 * 后端是**两段 multipart**:`file` 为二进制段,`data` 为另一个段且需带
 * Content-Type: application/json 才能反序列化成 TemplateCreateReqVO——
 * 不能当普通表单字段塞,也不能走 @RequestBody。
 */
export const createTemplate = async (file: File, data: Record<string, unknown>) => {
  const form = new FormData()
  form.append('file', file)
  form.append('data', new Blob([JSON.stringify(data)], { type: 'application/json' }))
  return await request.post({ url: '/business/templates/create', data: form })
}

/** 更新证书模板(id 走 query,体为规则字段) */
export const updateTemplate = async (id: number, data: any) => {
  return await request.put({ url: '/business/templates/update?id=' + id, data })
}

/** 删除证书模板 */
export const deleteTemplate = async (id: number) => {
  return await request.delete({ url: '/business/templates/delete?id=' + id })
}

/**
 * 回显模板样本图。
 * 端点是 inline(无 Content-Disposition,带 Cache-Control: no-store),但
 * **鉴权走 Authorization 头**,所以裸 `<img src>` 拼 URL 必然 401;
 * 必须走 request.download 取 Blob 再 createObjectURL,并在卸载时 revoke。
 */
export const getTemplateImageBlob = async (id: number) => {
  return await request.download({ url: '/business/templates/image?id=' + id })
}

/**
 * 模板试测(按已保存样本图跑 AI 抽取)。
 * 无 VO,Service 内部 Map 的键名即契约,两模式(fake/grpc)键集一致:
 *   mode: 'fake' | 'grpc'
 *   dataJson: string —— **JSON 字符串不是对象**,内层键无契约,须自行 parse
 *   ocrText: string  —— OCR 全文,后端不截断
 *   disclaimer: string
 * 无降级 Map:Worker 不可用时直接抛 4003,由 axios 拦截器转成 reject。
 */
export const testTemplate = async (id: number) => {
  return await request.post({ url: '/business/templates/test?id=' + id })
}

/**
 * 创建前 AI 抽取(不落库)。multipart 只有 file 一个段,ruleJson 走 form/query。
 * 返回键与 testTemplate 完全同名同类型。
 * @param ruleJson 规则 JSON 字符串,空则后端归一为 '{}',非法则报模板 JSON 非法
 */
export const extractForCreate = async (file: File, ruleJson?: string) => {
  const form = new FormData()
  form.append('file', file)
  if (ruleJson) {
    form.append('ruleJson', ruleJson)
  }
  return await request.post({ url: '/business/templates/extract-for-create', data: form })
}

/**
 * 生成抽取 prompt。键集比上面两个少两个:
 *   mode: 'fake' | 'grpc' / prompt: string / disclaimer: string
 * disclaimer 在 grpc 模式下优先取 Worker 返回值,前端不能硬编码。
 */
export const generatePrompt = async (params: { ruleJson?: string; sampleText?: string }) => {
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

/** 更新大创(id 走 query,体为待改字段,全部可空) */
export const updateInnovation = async (id: number, data: any) => {
  return await request.put({ url: '/business/innovations/update?id=' + id, data })
}

/**
 * 大创 xlsx 导入预览。
 * 表头必须严格等于:项目编号, 项目名称, 项目类型, 起始日期, 结束日期,
 * 负责人姓名, 负责人学号, 其他成员, 指导教师, 经费
 * (顺序、个数、名称全一致,否则整表结构拒绝);项目类型白名单 国家级/省级/院级;
 * 经费表头按**万元**填,后端 ×10000 存为元;最多 1000 行。
 * 返回 record ImportPreview(token, rowCount, errorCount, firstRowEcho, rows)
 * rows 每项 record ImportRow(rowNo, projectNo, projectName, projectType, startDate,
 * endDate, leaderName, leaderId, otherMembers, supervisors, funding, error)
 */
export const previewInnovationImport = async (file: File) => {
  const form = new FormData()
  form.append('file', file)
  return await request.post({ url: '/business/innovations/import/preview', data: form })
}

/** 大创 xlsx 导入确认(token 单次有效,用后即失效) */
export const confirmInnovationImport = async (token: string) => {
  return await request.post({ url: '/business/innovations/import/confirm', params: { token } })
}

/**
 * 大创状态批量校准(按 end_date 推导:严格早于今天才算已结题)。
 * 返回 record CalibrationResult(considered, calibrated, skippedUnparsed, calibratedIds)
 * calibratedIds 可直接回查哪些行被改了。
 */
export const calibrateInnovationStatus = async () => {
  return await request.post({ url: '/business/innovations/calibrate-status' })
}

// ==================== 统计分析 ====================

/** 获得统计总览(summary 五项 + category 五类计数) */
export const getStatsOverview = async () => {
  return await request.get({ url: '/business/stats/overview' })
}

/** 获得竞赛战果排行(服务端定页长,无分页参数;无竞赛关联的归入"未关联") */
export const getStatsByCompetition = async () => {
  return await request.get({ url: '/business/stats/by-competition' })
}

// ==================== 数据导出 ====================

/**
 * 以下四个端点都无查询参数,一律导出当前租户全量,返回二进制。
 * 服务端已写 UTF-8 BOM,CSV 在 Excel 里打开中文不乱码。
 * 行数超上限时返回 JSON 错误信封(1003009000),request.download 会读出并
 * 抛错提示给用户——v2 的裸 <a> 直链会把错误响应体当文件下载下来。
 */
export const exportCompetitionSummaryCsv = () => {
  return request.download({ url: '/business/export/competition-summary.csv' })
}

export const exportCompetitionSummaryXlsx = () => {
  return request.download({ url: '/business/export/competition-summary.xlsx' })
}

export const exportStudentAffairsCsv = () => {
  return request.download({ url: '/business/export/student-affairs.csv' })
}

export const exportStudentAffairsXlsx = () => {
  return request.download({ url: '/business/export/student-affairs.xlsx' })
}

// ==================== 业务日志 ====================

/**
 * 获得业务审计日志分页(只查 awardie_achievement_audit_log,即审核留痕;
 * 不含框架自身的登录/操作日志)。
 * 筛选项:achievementKind / actionType / operatorKeyword / createTime 区间。
 * changeDetail 是 JSON **字符串**,驳回原因只在这里,须自行 parse。
 */
export const getAuditLogPage = async (params: any) => {
  return await request.get({ url: '/business/logs/audit', params })
}
