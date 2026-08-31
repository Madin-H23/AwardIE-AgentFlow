package com.awardie.admin;

import java.util.List;
import java.util.Map;

import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;
import com.awardie.common.ApiResponse;

/** 大创 xlsx 导入(#34,对照 v1 成果/文件导入):preview 解析预览 → confirm 写库;幂等靠 project_no UNIQUE。 */
@RestController
@RequestMapping("/api/v2/admin/import")
public class AdminImportController {

    private final InnovationImportService service;
    private final UserRepository users;

    public AdminImportController(InnovationImportService service, UserRepository users) {
        this.service = service;
        this.users = users;
    }

    /** 预览:解析 xlsx 返回行级数据与校验错误(不写库)。 */
    @PostMapping("/innovation/preview")
    public ApiResponse<Map<String, Object>> preview(@RequestParam("file") MultipartFile file,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        return ApiResponse.ok(service.preview(file.getBytes()));
    }

    public record ConfirmRequest(String sha256, List<InnovationImportService.ImportRow> rows) {}

    /** 确认导入:仅写无 error 行;project_no 冲突跳过;留痕。 */
    @PostMapping("/innovation/confirm")
    public ApiResponse<InnovationImportService.ImportResult> confirm(@RequestBody ConfirmRequest req,
            Authentication auth) {
        requireAdmin(auth);
        UserEntity operator = users.findByLoginCode(auth.getName()).orElseThrow();
        return ApiResponse.ok(service.importRows(req.rows(), operator), "导入完成");
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
