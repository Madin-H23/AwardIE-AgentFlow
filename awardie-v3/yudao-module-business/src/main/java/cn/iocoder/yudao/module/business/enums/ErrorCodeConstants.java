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

}
