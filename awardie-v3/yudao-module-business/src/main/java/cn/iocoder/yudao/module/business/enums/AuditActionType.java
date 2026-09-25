package cn.iocoder.yudao.module.business.enums;

import java.util.Map;

/**
 * 业务审计动作码(批9)
 *
 * <p>只映射审核流实际产出的四个码。v2 基线表注释允许 1-12,但取证确认 v2 Java 只写
 * 1/6/7/8(编辑/删除/撤回等路径根本没调审计仓储),故不为未产出的码编造标签——
 * 未知码走 {@link #label(Integer)} 的兜底。
 *
 * @author AwardIE
 */
public interface AuditActionType {

    /** 动作码:提交成果 */
    int SUBMIT = 1;
    /** 动作码:审核通过 */
    int APPROVE = 6;
    /** 动作码:驳回 */
    int REJECT = 7;
    /** 动作码:物化入库 */
    int MATERIALIZE = 8;

    Map<Integer, String> LABELS = Map.of(
            SUBMIT, "提交成果",
            APPROVE, "审核通过",
            REJECT, "驳回",
            MATERIALIZE, "物化入库");

    /**
     * 动作码转中文标签
     *
     * @param actionType 动作码,可为 null
     * @return 中文标签;未知码返回"动作 {code}",null 返回空串(不编造)
     */
    static String label(Integer actionType) {
        if (actionType == null) {
            return "";
        }
        return LABELS.getOrDefault(actionType, "动作 " + actionType);
    }

}
