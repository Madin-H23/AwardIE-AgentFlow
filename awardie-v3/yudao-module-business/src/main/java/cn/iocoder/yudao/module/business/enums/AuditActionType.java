package cn.iocoder.yudao.module.business.enums;

import cn.iocoder.yudao.framework.common.core.ArrayValuable;

import java.util.Arrays;
import java.util.Map;

/**
 * 业务审计动作码(批9;批27 D-21 由接口转枚举,实现 ArrayValuable 供 @InEnum 校验过滤参数)
 *
 * <p>只映射审核流实际产出的四个码。v2 基线表注释允许 1-12,但取证确认 v2 Java 只写
 * 1/6/7/8(编辑/删除/撤回等路径根本没调审计仓储),故不为未产出的码编造标签——
 * 未知码走 {@link #label(Integer)} 的兜底。
 *
 * @author AwardIE
 */
public enum AuditActionType implements ArrayValuable<Integer> {

    /** 动作码:提交成果 */
    SUBMIT(1),
    /** 动作码:审核通过 */
    APPROVE(6),
    /** 动作码:驳回 */
    REJECT(7),
    /** 动作码:物化入库 */
    MATERIALIZE(8);

    /**
     * 全部合法动作码。@InEnum 校验器从枚举常量取 array(),且要求至少一个常量,
     * 故不允许做成"零常量仅静态值"的形态。
     */
    public static final Integer[] ARRAYS =
            Arrays.stream(values()).map(AuditActionType::getCode).toArray(Integer[]::new);

    /**
     * 动作码
     */
    private final int code;

    AuditActionType(int code) {
        this.code = code;
    }

    public int getCode() {
        return code;
    }

    @Override
    public Integer[] array() {
        return ARRAYS;
    }

    private static final Map<Integer, String> LABELS = Map.of(
            SUBMIT.getCode(), "提交成果",
            APPROVE.getCode(), "审核通过",
            REJECT.getCode(), "驳回",
            MATERIALIZE.getCode(), "物化入库");

    /**
     * 动作码转中文标签
     *
     * @param actionType 动作码,可为 null
     * @return 中文标签;未知码返回"动作 {code}",null 返回空串(不编造)
     */
    public static String label(Integer actionType) {
        if (actionType == null) {
            return "";
        }
        return LABELS.getOrDefault(actionType, "动作 " + actionType);
    }

}
