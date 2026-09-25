package cn.iocoder.yudao.module.business.enums;

import cn.iocoder.yudao.framework.common.exception.ErrorCode;

/**
 * AwardIE 业务模块错误码(编号段 1_003,继 infra 1_001 / system 1_002 之后;
 * 各业务域按 1_003_00X_000 分段,芋道 codegen 约定)。
 *
 * @author AwardIE
 */
public interface ErrorCodeConstants {

    // ========== AwardIE 实验室 1_003_000_000 ==========
    /** AwardIE 实验室不存在 */
    ErrorCode LABORATORIES_NOT_EXISTS = new ErrorCode(1_003_000_000, "AwardIE 实验室不存在");
    /** AwardIE 实验室名称已存在 */
    ErrorCode LABORATORIES_NAME_DUPLICATE = new ErrorCode(1_003_000_001, "实验室名称已存在");
    /** AwardIE 实验室存在关联数据,无法删除(参数=引用明细) */
    ErrorCode LABORATORIES_IN_USE = new ErrorCode(1_003_000_002, "实验室无法删除,{}");
    /** AwardIE 实验室单次批量删除条数超限 */
    ErrorCode LABORATORIES_DELETE_TOO_MANY = new ErrorCode(1_003_000_003, "单次最多删除 1000 个实验室");

    // ========== AwardIE 竞赛 1_003_001_000 ==========
    /** AwardIE 竞赛不存在 */
    ErrorCode COMPETITIONS_NOT_EXISTS = new ErrorCode(1_003_001_000, "AwardIE 竞赛不存在");
    /** AwardIE 竞赛名称已存在 */
    ErrorCode COMPETITIONS_NAME_DUPLICATE = new ErrorCode(1_003_001_001, "竞赛名称已存在");
    /** AwardIE 竞赛存在关联数据,无法删除(参数=引用明细) */
    ErrorCode COMPETITIONS_IN_USE = new ErrorCode(1_003_001_002, "竞赛无法删除,{}");
    /** AwardIE 竞赛单次批量删除条数超限 */
    ErrorCode COMPETITIONS_DELETE_TOO_MANY = new ErrorCode(1_003_001_003, "单次最多删除 1000 个竞赛");

    // ========== AwardIE 待审成果 1_003_002_000 ==========
    /** 待审成果不存在 */
    ErrorCode PENDING_ACHIEVEMENT_NOT_EXISTS = new ErrorCode(1_003_002_000, "待审成果不存在");
    /** 同一文件已在待审列表中(sha256 去重) */
    ErrorCode PENDING_ACHIEVEMENT_DUPLICATE_FILE =
            new ErrorCode(1_003_002_001, "该文件已在待审列表中(内容重复)");
    /** 仅待审状态可撤回 */
    ErrorCode PENDING_ACHIEVEMENT_NOT_WITHDRAWABLE =
            new ErrorCode(1_003_002_003, "仅待审状态可撤回");
    /** 无权操作他人提交 */
    ErrorCode PENDING_ACHIEVEMENT_FORBIDDEN = new ErrorCode(1_003_002_004, "无权操作他人的提交");
    /** 未知成果类型 */
    ErrorCode PENDING_ACHIEVEMENT_TYPE_UNKNOWN = new ErrorCode(1_003_002_005, "未知成果类型");

    // ========== AwardIE 文件域 1_003_003_000 ==========
    /** 文件类型不在白名单 */
    ErrorCode FILE_TYPE_NOT_ALLOWED =
            new ErrorCode(1_003_003_000, "不支持的文件类型,仅允许 jpg/jpeg/png/pdf");
    /** 文件超过大小上限 */
    ErrorCode FILE_TOO_LARGE = new ErrorCode(1_003_003_001, "文件超过 10MB 上限");
    /** 文件内容与扩展名不符 */
    ErrorCode FILE_CONTENT_MISMATCH = new ErrorCode(1_003_003_002, "文件内容与扩展名不符(魔术字节校验失败)");
    /** 非法文件路径(目录穿越) */
    ErrorCode FILE_PATH_ILLEGAL = new ErrorCode(1_003_003_003, "非法文件路径");

    // ========== AwardIE 审核流 1_003_004_000 ==========
    /** 审核状态机非法流转(仅 pending 可审) */
    ErrorCode REVIEW_ILLEGAL_STATE_TRANSITION =
            new ErrorCode(1_003_004_000, "当前状态不可审核:{}");
    /** 驳回必须填写原因(BR-5) */
    ErrorCode REVIEW_COMMENT_REQUIRED = new ErrorCode(1_003_004_001, "驳回必须填写原因");
    /** 无权查看他人审核时间线 */
    ErrorCode REVIEW_TIMELINE_FORBIDDEN = new ErrorCode(1_003_004_002, "无权查看他人的审核时间线");
    /** 审核动作非法(仅 approve/reject) */
    ErrorCode REVIEW_ACTION_INVALID = new ErrorCode(1_003_004_003, "审核动作仅允许 approve/reject");

    // ========== AwardIE 成果库 1_003_005_000 ==========
    /** 成果库类型非法(仅 award/patent/software/innovation/other) */
    ErrorCode VAULT_TYPE_INVALID =
            new ErrorCode(1_003_005_000, "type 仅允许 award/patent/software/innovation/other");
    /** 成果库记录不存在 */
    ErrorCode VAULT_RECORD_NOT_EXISTS = new ErrorCode(1_003_005_001, "成果记录不存在");
    /** 成果库记录存在关联数据,无法删除 */
    ErrorCode VAULT_RECORD_IN_USE = new ErrorCode(1_003_005_002, "成果存在关联数据,无法删除:{}");

    // ========== AwardIE 证书模板 1_003_006_000 ==========
    /** 证书模板不存在 */
    ErrorCode TEMPLATE_NOT_EXISTS = new ErrorCode(1_003_006_000, "证书模板不存在");
    /** 同竞赛 + 同授予角色已存在模板 */
    ErrorCode TEMPLATE_DUPLICATE_ROLE = new ErrorCode(1_003_006_001, "该竞赛的该授予角色已存在模板");
    /** 授予角色非法(仅学生/教师) */
    ErrorCode TEMPLATE_ROLE_INVALID = new ErrorCode(1_003_006_002, "授予角色必须是学生或教师");
    /** 规则字段 JSON 格式非法 */
    ErrorCode TEMPLATE_JSON_INVALID = new ErrorCode(1_003_006_003, "规则字段 JSON 格式非法:{}");
    /** 模板规则字段取值非法(长度区间反向/负数等) */
    ErrorCode TEMPLATE_RULE_INVALID = new ErrorCode(1_003_006_004, "模板规则字段不合法:{}");
    /** 模板无样本图(无法试测) */
    ErrorCode TEMPLATE_SAMPLE_IMAGE_MISSING = new ErrorCode(1_003_006_005, "该模板没有样本图片,无法试测");
    /** 样本图物理文件已失存 */
    ErrorCode TEMPLATE_SAMPLE_IMAGE_LOST = new ErrorCode(1_003_006_006, "样本图文件缺失");

    // ========== AwardIE AI Worker 1_003_007_000 ==========
    /** AI Worker 不可用(gRPC 连接失败/超时/流中断) */
    ErrorCode AI_WORKER_UNAVAILABLE = new ErrorCode(1_003_007_000, "AI Worker 不可用({}),请稍后重试");

    // ========== AwardIE 大创 1_003_008_000 ==========
    /** 大创项目不存在 */
    ErrorCode INNOVATION_NOT_EXISTS = new ErrorCode(1_003_008_000, "大创项目不存在");
    /** 大创项目状态非法(仅进行中/已结题/终止) */
    ErrorCode INNOVATION_STATUS_INVALID =
            new ErrorCode(1_003_008_001, "项目状态非法,仅允许 进行中/已结题/终止");
    /** 大创项目类型非法(仅国家级/省级/院级) */
    ErrorCode INNOVATION_TYPE_INVALID =
            new ErrorCode(1_003_008_002, "项目类型非法,仅允许 国家级/省级/院级");
    /** 项目编号重复(导入幂等判据) */
    ErrorCode INNOVATION_NO_DUPLICATE = new ErrorCode(1_003_008_003, "项目编号 {} 已存在,跳过");
    /** 导入预览令牌无效/已过期/已使用 */
    ErrorCode INNOVATION_PREVIEW_INVALID =
            new ErrorCode(1_003_008_004, "预览已失效或已被使用,请重新上传文件");
    /** 导入文件行数超限 */
    ErrorCode INNOVATION_IMPORT_TOO_MANY_ROWS =
            new ErrorCode(1_003_008_005, "导入行数超过上限 {} 行");
    /** 导入文件表头不匹配 */
    ErrorCode INNOVATION_IMPORT_BAD_HEADER =
            new ErrorCode(1_003_008_006, "表头不匹配,应为 项目编号|项目名称|项目类型|起始日期|结束日期|负责人姓名|负责人学号|其他成员|指导教师|经费");
    /** 导入文件无法解析 */
    ErrorCode INNOVATION_IMPORT_PARSE_FAILED =
            new ErrorCode(1_003_008_007, "导入文件解析失败,请确认为合法的 xlsx");
    /** 项目名称为空 */
    ErrorCode INNOVATION_NAME_REQUIRED = new ErrorCode(1_003_008_008, "项目名称不能为空");
    /** 经费非法(非数字) */
    ErrorCode INNOVATION_FUNDING_INVALID = new ErrorCode(1_003_008_009, "经费格式非法,应为数字");

}
