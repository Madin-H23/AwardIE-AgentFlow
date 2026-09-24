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

}
