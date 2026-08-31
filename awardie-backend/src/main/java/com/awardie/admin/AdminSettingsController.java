package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;

/** 系统设置(#32,对照 v1 settings.html):自动归档开关矩阵真读写;通用/供应商分区为只读信息卡(外部化配置,见对照记录)。 */
@RestController
@RequestMapping("/api/v2/admin/settings")
public class AdminSettingsController {

    public record AutoArchiveRow(String achievementType, String validationStatus, boolean autoArchiveEnabled) {}

    public record AutoArchiveUpdate(List<AutoArchiveRow> rows) {}

    private final JdbcTemplate jdbc;

    public AdminSettingsController(JdbcTemplate jdbc) {
        this.jdbc = jdbc;
    }

    @GetMapping("/auto-archive")
    public ApiResponse<List<Map<String, Object>>> getAutoArchive(Authentication auth) {
        requireAdmin(auth);
        return ApiResponse.ok(jdbc.queryForList("""
                SELECT achievement_type, validation_status, auto_archive_enabled
                FROM auto_archive_config ORDER BY achievement_type, validation_status NULLS LAST
                """));
    }

    /** 批量更新:仅允许改 auto_archive_enabled,键(类型×状态)不可变。 */
    @PutMapping("/auto-archive")
    public ApiResponse<Integer> updateAutoArchive(@RequestBody AutoArchiveUpdate req, Authentication auth) {
        requireAdmin(auth);
        int updated = 0;
        for (AutoArchiveRow row : req.rows()) {
            updated += jdbc.update(
                    "UPDATE auto_archive_config SET auto_archive_enabled=?, updated_at=NOW() "
                            + "WHERE achievement_type=? AND ((validation_status IS NULL AND ? IS NULL) OR validation_status=?)",
                    row.autoArchiveEnabled(), row.achievementType(), row.validationStatus(), row.validationStatus());
        }
        return ApiResponse.ok(updated, "已保存");
    }

    private void requireAdmin(Authentication auth) {
        for (GrantedAuthority a : auth.getAuthorities()) {
            if (a.getAuthority().equals("ROLE_ADMIN")) {
                return;
            }
        }
        throw new org.springframework.security.access.AccessDeniedException("需要 admin 角色");
    }
}
