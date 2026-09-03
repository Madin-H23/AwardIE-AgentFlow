// UX-1 批3:成果类型/提交状态的中文徽章映射(单一真源,列表页族共用)。
// 消灭诊断 B2:pending/archived/award 等工程值直出;色板消费 tokens --tag-* 语义。
export const ACHIEVEMENT_TYPE_LABELS: Record<string, string> = {
  award: '奖状',
  patent: '专利',
  software: '软著',
  innovation: '大创',
  other: '其他',
}

export const STATUS_LABELS: Record<string, string> = {
  pending: '待审',
  archived: '已归档',
  rejected: '已驳回',
}

export function typeLabel(v: unknown): string {
  return ACHIEVEMENT_TYPE_LABELS[String(v ?? '')] ?? String(v ?? '-')
}

export function statusLabel(v: unknown): string {
  return STATUS_LABELS[String(v ?? '')] ?? String(v ?? '-')
}

/** 状态 → el-tag type(未知值兜底 info;查表避免嵌套三元)。 */
const STATUS_TAG_TYPES: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'warning',
  archived: 'success',
  rejected: 'danger',
}

export function statusTagType(v: unknown): 'success' | 'warning' | 'danger' | 'info' {
  return STATUS_TAG_TYPES[String(v ?? '')] ?? 'info'
}

export const SUBMITTER_TYPE_LABELS: Record<string, string> = {
  student: '学生',
  teacher: '教师',
  admin: '管理员',
}

export function submitterTypeLabel(v: unknown): string {
  return SUBMITTER_TYPE_LABELS[String(v ?? '')] ?? String(v ?? '-')
}
