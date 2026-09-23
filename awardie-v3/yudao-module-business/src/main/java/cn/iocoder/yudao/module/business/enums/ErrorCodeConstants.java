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

}
