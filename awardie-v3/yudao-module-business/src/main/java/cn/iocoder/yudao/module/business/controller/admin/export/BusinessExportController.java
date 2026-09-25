package cn.iocoder.yudao.module.business.controller.admin.export;

import cn.iocoder.yudao.framework.apilog.core.annotation.ApiAccessLog;
import cn.iocoder.yudao.framework.common.util.http.HttpUtils;
import cn.iocoder.yudao.framework.excel.core.util.ExcelUtils;
import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.service.export.BusinessExportService;
import cn.iocoder.yudao.module.business.service.export.CompetitionSummaryRow;
import cn.iocoder.yudao.module.business.service.export.CsvWriter;
import cn.iocoder.yudao.module.business.service.export.StudentAwardRow;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.annotation.Resource;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.io.IOException;
import java.time.LocalDate;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

import static cn.iocoder.yudao.framework.apilog.core.enums.OperateTypeEnum.EXPORT;

/**
 * 管理后台 - 数据导出(批9)
 *
 * <p>两类导出各支持 CSV 与 XLSX。CSV 走 {@link CsvWriter}(UTF-8 BOM + 公式注入防护 +
 * RFC4180 转义),XLSX 走已有 FastExcel starter 的动态表头重载。
 *
 * <p>教师个人导出暂缺(需教师关系表,前置债),学生个人导出属批10 学生端门户。
 *
 * @author AwardIE
 */
@Tag(name = "管理后台 - AwardIE 数据导出")
@RestController
@RequestMapping("/business/export")
@Validated
public class BusinessExportController {

    @Resource
    private BusinessExportService exportService;

    @GetMapping("/competition-summary.csv")
    @Operation(summary = "导出竞赛年度汇总(CSV)")
    @ApiAccessLog(operateType = EXPORT, operateName = "导出竞赛年度汇总CSV")
    @PreAuthorize("@ss.hasPermission('business:export:query')")
    public void exportCompetitionSummaryCsv(HttpServletResponse response) throws IOException {
        writeCsv(response, "competition-summary",
                BusinessExportService.competitionSummaryHeader(),
                BusinessExportService.competitionSummaryCells(
                        exportService.getCompetitionSummary(currentTenantId())));
    }

    @GetMapping("/competition-summary.xlsx")
    @Operation(summary = "导出竞赛年度汇总(XLSX)")
    @ApiAccessLog(operateType = EXPORT, operateName = "导出竞赛年度汇总XLSX")
    @PreAuthorize("@ss.hasPermission('business:export:query')")
    public void exportCompetitionSummaryXlsx(HttpServletResponse response) throws IOException {
        writeXlsx(response, "competition-summary", "竞赛年度汇总",
                BusinessExportService.competitionSummaryHeader(),
                BusinessExportService.competitionSummaryCells(
                        exportService.getCompetitionSummary(currentTenantId())));
    }

    @GetMapping("/student-affairs.csv")
    @Operation(summary = "导出学生获奖明细(CSV)")
    @ApiAccessLog(operateType = EXPORT, operateName = "导出学生获奖明细CSV")
    @PreAuthorize("@ss.hasPermission('business:export:query')")
    public void exportStudentAffairsCsv(HttpServletResponse response) throws IOException {
        writeCsv(response, "student-affairs",
                BusinessExportService.studentAffairsHeader(),
                BusinessExportService.studentAffairsCells(
                        exportService.getStudentAffairs(currentTenantId())));
    }

    @GetMapping("/student-affairs.xlsx")
    @Operation(summary = "导出学生获奖明细(XLSX)")
    @ApiAccessLog(operateType = EXPORT, operateName = "导出学生获奖明细XLSX")
    @PreAuthorize("@ss.hasPermission('business:export:query')")
    public void exportStudentAffairsXlsx(HttpServletResponse response) throws IOException {
        writeXlsx(response, "student-affairs", "学生获奖明细",
                BusinessExportService.studentAffairsHeader(),
                BusinessExportService.studentAffairsCells(
                        exportService.getStudentAffairs(currentTenantId())));
    }

    /**
     * 写 CSV
     *
     * <p>不用芋道 ServletUtils:它只封装了 xlsx 与 JSON,无 CSV。文件名统一
     * {@code 名称-日期.csv} 并显式带 UTF-8 BOM——Excel 靠 BOM 识别编码,缺失则中文乱码。
     *
     * @param response 响应
     * @param name     文件名主干(不含日期与扩展名)
     * @param header   表头
     * @param rows     数据行
     * @throws IOException 写响应失败
     */
    private void writeCsv(HttpServletResponse response, String name, String[] header, List<String[]> rows)
            throws IOException {
        response.setContentType("text/csv;charset=UTF-8");
        response.setCharacterEncoding("utf-8");
        String filename = name + "-" + LocalDate.now() + ".csv";
        response.setHeader("Content-Disposition",
                "attachment;filename=\"" + filename + "\"; filename*=UTF-8''"
                        + HttpUtils.encodeUtf8(filename));
        response.getOutputStream().write(CsvWriter.write(header, rows));
        response.getOutputStream().flush();
    }

    /**
     * 写 XLSX(动态表头,无需为每个导出定义 DTO 类)
     *
     * @param response  响应
     * @param name      文件名主干
     * @param sheet     sheet 名
     * @param header    表头
     * @param rows      数据行
     * @throws IOException 写响应失败
     */
    private void writeXlsx(HttpServletResponse response, String name, String sheet, String[] header,
            List<String[]> rows) throws IOException {
        List<List<String>> head = new ArrayList<>(1);
        head.add(Arrays.asList(header));
        List<List<Object>> data = new ArrayList<>(rows.size());
        for (String[] row : rows) {
            data.add(Arrays.asList((Object[]) row));
        }
        // 文件名必须带 .xlsx:浏览器会优先采用 Content-Disposition 的名字,
        // 缺扩展名会存成无后缀文件(同仓 CompetitionsController/LaboratoriesController 均带扩展名)
        ExcelUtils.write(response, name + "-" + LocalDate.now() + ".xlsx", sheet, head, data);
    }

    private Long currentTenantId() {
        return TenantContextHolder.getRequiredTenantId();
    }

}
