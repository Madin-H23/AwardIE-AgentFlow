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
    private final com.awardie.admin.BatchImportService batchService;
    private final UserRepository users;

    public AdminImportController(InnovationImportService service,
            com.awardie.admin.BatchImportService batchService, UserRepository users) {
        this.service = service;
        this.batchService = batchService;
        this.users = users;
    }

    /** 预览:解析 xlsx 返回行级数据与校验错误(不写库)。 */
    @PostMapping("/innovation/preview")
    public ApiResponse<Map<String, Object>> preview(@RequestParam("file") MultipartFile file,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        return ApiResponse.ok(service.preview(file.getBytes()));
    }

    /** 图片批量导入(#40,对照 v1 自动导入):多图逐张走三校验/存储/去重,admin pending 归档。 */
    @PostMapping("/awards/batch")
    public ApiResponse<List<com.awardie.admin.BatchImportService.BatchItem>> importBatch(
            @RequestParam("files") org.springframework.web.multipart.MultipartFile[] files,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        if (files.length == 0) {
            return ApiResponse.error(4000, "请选择至少一个文件");
        }
        if (files.length > 20) {
            return ApiResponse.error(4000, "单批最多 20 个文件");
        }
        UserEntity operator = users.findByLoginCode(auth.getName()).orElseThrow();
        List<byte[]> bytes = new java.util.ArrayList<>();
        List<String> names = new java.util.ArrayList<>();
        for (MultipartFile f : files) {
            bytes.add(f.getBytes());
            names.add(f.getOriginalFilename() == null ? "unnamed" : f.getOriginalFilename());
        }
        return ApiResponse.ok(batchService.importBatch(bytes, names, operator));
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
