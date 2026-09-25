package cn.iocoder.yudao.module.business.service.innovation;

import cn.idev.excel.annotation.ExcelProperty;
import lombok.Data;

/**
 * 大创导入 xlsx 行 DTO(批8)
 *
 * <p>用强类型读取(而非按列下标读 Map)的原因:动态读取拿不到表头文字,
 * **无法校验表头是否正确**——管理员传一份列序调换或表头改字的表,系统会静默按位置读错。
 * 强类型读取让 FastExcel 按 {@link ExcelProperty} 里的名字匹配表头,
 * 匹配不上即报错,把"人眼核对表头"变成"系统强制校验"(批8 决策,方案一)。
 *
 * <p>两处刻意的取舍:
 * <ol>
 *   <li>列名写死十项:与导入页列序说明、{@link InnovationImportService#EXPECTED_HEADER} 三处一致;</li>
 *   <li>字段全 String:Excel 的日期与数字列常被读成序列号或科学计数,
 *       统一按字符串接再逐字段解析(沿 v2 口径,但不再静默)。</li>
 * </ol>
 *
 * @author AwardIE
 */
@Data
public class InnovationImportRow {

    @ExcelProperty("项目编号")
    private String projectNo;

    @ExcelProperty("项目名称")
    private String projectName;

    @ExcelProperty("项目类型")
    private String projectType;

    @ExcelProperty("起始日期")
    private String startDate;

    @ExcelProperty("结束日期")
    private String endDate;

    @ExcelProperty("负责人姓名")
    private String leaderName;

    @ExcelProperty("负责人学号")
    private String leaderId;

    @ExcelProperty("其他成员")
    private String otherMembers;

    @ExcelProperty("指导教师")
    private String supervisors;

    @ExcelProperty("经费")
    private String funding;

}
