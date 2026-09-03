package com.awardie.admin;

import java.nio.charset.StandardCharsets;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import com.awardie.aireview.AiWorkerClient;
import com.awardie.common.ApiResponse;
import com.fasterxml.jackson.databind.ObjectMapper;

import io.grpc.StatusRuntimeException;

/** Fix-TP:奖状模板创建/详情/试测端点(对照 v1 admin_templates create/update/test/image)。 */
@RestController
@RequestMapping("/api/v2/admin/templates")
public class AdminTemplateDetailController {

    private final JdbcTemplate jdbc;
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final boolean aiFake;
    private final AiWorkerClient aiClient;

    public AdminTemplateDetailController(JdbcTemplate jdbc,
            @Value("${ai.worker.mode:fake}") String aiMode,
            AiWorkerClient aiClient) {
        this.jdbc = jdbc;
        this.aiFake = "fake".equalsIgnoreCase(aiMode);
        this.aiClient = aiClient;
    }

    /** 创建模板(multipart:样本图必填;唯一性=同竞赛同角色,v1 manager 层查重的 SQL 化)。 */
    @PostMapping("/create")
    @Transactional
    public ApiResponse<Integer> create(
            @RequestParam("file") MultipartFile file,
            @RequestParam("competitionId") Integer competitionId,
            @RequestParam String grantedRole,
            @RequestParam(required = false) String sampleExtracted,
            @RequestParam(required = false) String sampleText,
            @RequestParam(required = false) String keywords,
            @RequestParam(defaultValue = "zh") String language,
            @RequestParam(defaultValue = "false") boolean needTranslate,
            @RequestParam(defaultValue = "0") int minLength,
            @RequestParam(required = false) Integer maxLength,
            @RequestParam(required = false) String defaultFields,
            @RequestParam(required = false) String llmFields,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        if (file == null || file.isEmpty()) {
            return ApiResponse.error(4000, "请上传样本图片");
        }
        if (!"学生".equals(grantedRole) && !"教师".equals(grantedRole)) {
            return ApiResponse.error(4000, "授予角色必须是学生或教师");
        }
        try {
            normalizeJson(sampleExtracted);
            normalizeJson(defaultFields);
            normalizeJson(llmFields);
        } catch (IllegalArgumentException e) {
            return ApiResponse.error(4000, e.getMessage());
        }
        Integer comp = jdbc.queryForObject(
                "SELECT COUNT(*) FROM competitions WHERE id = ?", Integer.class, competitionId);
        if (comp == null || comp == 0) {
            return ApiResponse.error(4004, "竞赛不存在");
        }
        Integer dup = jdbc.queryForObject(
                "SELECT COUNT(*) FROM templates WHERE competition_id = ? AND default_fields->>'granted_role' = ?",
                Integer.class, competitionId, grantedRole);
        if (dup != null && dup > 0) {
            return ApiResponse.error(4009, "该竞赛已有相同角色的模板");
        }
        Map<String, Object> df = parseJson(defaultFields, new LinkedHashMap<>());
        df.put("granted_role", grantedRole);
        List<String> kw = splitLines(keywords);
        if (kw.isEmpty()) {
            String compName = jdbc.queryForObject(
                    "SELECT competition_name FROM competitions WHERE id = ?", String.class, competitionId);
            kw = new java.util.ArrayList<>();
            kw.add(compName);
        }
        jdbc.update("""
                INSERT INTO templates (template_type, min_length, max_length, keywords, sample_text,
                       sample_extracted, default_fields, llm_fields, language, need_translate,
                       is_manual_edited, competition_id)
                VALUES ('AWARD', ?, ?, CAST(? AS jsonb), ?, CAST(? AS jsonb), CAST(? AS jsonb),
                        CAST(? AS jsonb), ?, ?, TRUE, ?)
                """, minLength, maxLength == null ? 0 : maxLength,
                objectMapper.writeValueAsString(kw), blankToNull(sampleText),
                normalizeJson(sampleExtracted), objectMapper.writeValueAsString(df),
                normalizeJson(llmFields), blankToNull(language) == null ? "zh" : language,
                needTranslate, competitionId);
        Integer newId = jdbc.queryForObject(
                "SELECT id FROM templates WHERE competition_id = ? AND default_fields->>'granted_role' = ? "
                        + "ORDER BY id DESC LIMIT 1", Integer.class, competitionId, grantedRole);
        byte[] blob = file.getBytes();
        jdbc.update("UPDATE templates SET sample_image_blob = ? WHERE id = ?", blob, newId);
        return ApiResponse.ok(newId, "创建成功");
    }

    /** 详情聚合:全字段(不含 blob,含 hasImage)。 */
    @GetMapping("/{id}/detail")
    public ApiResponse<Map<String, Object>> detail(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        List<Map<String, Object>> rows = jdbc.queryForList("""
                SELECT t.id, t.template_type AS "templateType", t.min_length AS "minLength",
                       t.max_length AS "maxLength", t.keywords::TEXT AS "keywords",
                       t.sample_text AS "sampleText", t.sample_extracted::TEXT AS "sampleExtracted",
                       t.default_fields::TEXT AS "defaultFields", t.llm_fields::TEXT AS "llmFields",
                       t.language, t.need_translate AS "needTranslate",
                       (t.sample_image_blob IS NOT NULL) AS "hasImage",
                       t.competition_id AS "competitionId",
                       c.competition_name AS "competitionName"
                FROM templates t LEFT JOIN competitions c ON t.competition_id = c.id
                WHERE t.id = ?
                """, id);
        if (rows.isEmpty()) {
            return ApiResponse.error(4004, "模板不存在");
        }
        return ApiResponse.ok(rows.get(0));
    }

    /** 全字段更新(keywords=字符串数组;JSONB 列 CAST 写入)。 */
    public record TemplateUpdate(Integer minLength, Integer maxLength, List<String> keywords, String sampleText,
            String sampleExtracted, String defaultFields, String llmFields, String language,
            boolean needTranslate) {}

    @PutMapping("/{id}")
    @Transactional
    public ApiResponse<Integer> update(@PathVariable Integer id, @RequestBody TemplateUpdate req,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        List<String> kw = req.keywords() == null ? List.of()
                : req.keywords().stream().filter(s -> s != null && !s.isBlank()).map(String::trim).toList();
        jdbc.update("""
                UPDATE templates SET min_length = ?, max_length = ?, keywords = CAST(? AS jsonb),
                       sample_text = ?, sample_extracted = CAST(? AS jsonb),
                       default_fields = CAST(? AS jsonb), llm_fields = CAST(? AS jsonb),
                       language = ?, need_translate = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """, req.minLength() == null ? 0 : req.minLength(),
                req.maxLength() == null ? 0 : req.maxLength(),
                objectMapper.writeValueAsString(kw), blankToNull(req.sampleText()),
                normalizeJson(req.sampleExtracted()), normalizeJson(req.defaultFields()),
                normalizeJson(req.llmFields()), blankToNull(req.language()) == null ? "zh" : req.language(),
                req.needTranslate(), id);
        Integer n = jdbc.queryForObject("SELECT COUNT(*) FROM templates WHERE id = ?", Integer.class, id);
        if (n == null || n == 0) {
            return ApiResponse.error(4004, "模板不存在");
        }
        return ApiResponse.ok(1, "已更新");
    }

    /** 样本图回显:按文件头判 Content-Type。 */
    @GetMapping("/{id}/image")
    public ResponseEntity<byte[]> image(@PathVariable Integer id, Authentication auth) throws Exception {
        requireAdmin(auth);
        List<byte[]> rows = jdbc.queryForList(
                "SELECT sample_image_blob FROM templates WHERE id = ?", byte[].class, id);
        if (rows.isEmpty() || rows.get(0) == null) {
            return ResponseEntity.notFound().build();
        }
        byte[] bytes = rows.get(0);
        String type = "application/octet-stream";
        if (bytes.length > 3 && (bytes[0] & 0xFF) == 0xFF && (bytes[1] & 0xFF) == 0xD8) {
            type = "image/jpeg";
        } else if (bytes.length > 4 && (bytes[0] & 0xFF) == 0x89 && bytes[1] == 'P') {
            type = "image/png";
        }
        return ResponseEntity.ok().header("Content-Type", type).body(bytes);
    }

    /** 模板试测:fake=确定性桩(回显 sample_extracted);模板试测(OCR+匹配+抽取)待页面批次接 ExtractTemplate。 */
    @PostMapping("/{id}/test")
    public ApiResponse<Map<String, Object>> test(@PathVariable Integer id, Authentication auth) {
        requireAdmin(auth);
        if (!aiFake) {
            return ApiResponse.error(4003, "模板试测待接入 ExtractTemplate(页面批次)");
        }
        List<Map<String, Object>> rows = jdbc.queryForList(
                "SELECT sample_extracted::TEXT AS se FROM templates WHERE id = ?", id);
        if (rows.isEmpty()) {
            return ApiResponse.error(4004, "模板不存在");
        }
        Map<String, Object> out = new LinkedHashMap<>();
        out.put("mode", "fake");
        out.put("fields", rows.get(0).get("se"));
        out.put("ocrText", jdbc.queryForObject(
                "SELECT COALESCE(sample_text, '') FROM templates WHERE id = ?", String.class, id));
        return ApiResponse.ok(out);
    }

    /** 样本图抽取(架构票《AI Worker extract/prompt RPC 扩展》落地):fake=确定性桩,grpc=ExtractTemplate 契约。对照 v1 extract-for-create。 */
    @PostMapping("/extract-for-create")
    public ApiResponse<Map<String, Object>> extractForCreate(
            @RequestParam(value = "file", required = false) MultipartFile file,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        if (file == null || file.isEmpty()) {
            return ApiResponse.error(4000, "请上传样本图片");
        }
        String traceId = "tpl-extract-" + UUID.randomUUID().toString().substring(0, 8);
        Map<String, Object> out = new LinkedHashMap<>();
        if (aiFake) {
            out.put("mode", "fake");
            out.put("dataJson",
                    "{\"竞赛名称\":\"示例竞赛(fake 桩)\",\"获奖等级\":\"一等奖\",\"获奖人\":\"示例获奖人\"}");
            out.put("ocrText", "【fake 桩】样本 OCR 文本(接入真 Worker 后返回实际识别内容)。");
            return ApiResponse.ok(out);
        }
        try {
            var resp = aiClient.extractTemplate(file.getBytes(), file.getOriginalFilename(), "{}",
                    true, true, traceId, 120);
            if (resp.getCode() != 0) {
                return ApiResponse.error(resp.getCode(), resp.getMessage());
            }
            out.put("mode", "grpc");
            out.put("dataJson", resp.getDataJson());
            out.put("ocrText", resp.getOcrText());
            return ApiResponse.ok(out);
        } catch (StatusRuntimeException e) {
            return ApiResponse.error(4003, "AI Worker 不可用(" + e.getStatus().getCode() + "),请稍后重试");
        }
    }

    /** 模板 prompt 生成(架构票落地):fake=确定性桩,grpc=GeneratePrompt 契约。对照 v1 generate-prompt-for-create(表单平铺 body)。 */
    @PostMapping("/generate-prompt-for-create")
    public ApiResponse<Map<String, Object>> generatePromptForCreate(@RequestBody Map<String, Object> body,
            Authentication auth) throws Exception {
        requireAdmin(auth);
        String traceId = "tpl-prompt-" + UUID.randomUUID().toString().substring(0, 8);
        Map<String, Object> rule = new LinkedHashMap<>();
        for (String k : List.of("keywords", "sample_extracted", "default_fields", "llm_fields",
                "min_length", "max_length", "language", "need_translate")) {
            if (body.containsKey(k)) {
                rule.put(k, body.get(k));
            }
        }
        String sampleText = body.get("sample_text") == null ? "" : String.valueOf(body.get("sample_text"));
        Map<String, Object> out = new LinkedHashMap<>();
        if (aiFake) {
            out.put("mode", "fake");
            out.put("prompt", "【fake 桩】请从以下 OCR 文本抽取竞赛名称/获奖等级/获奖人字段并以 JSON 输出:"
                    + sampleText);
            return ApiResponse.ok(out);
        }
        try {
            var resp = aiClient.generatePrompt(objectMapper.writeValueAsString(rule), sampleText, traceId, 60);
            if (resp.getCode() != 0) {
                return ApiResponse.error(resp.getCode(), resp.getMessage());
            }
            out.put("mode", "grpc");
            out.put("prompt", resp.getPrompt());
            out.put("disclaimer", resp.getDisclaimer());
            return ApiResponse.ok(out);
        } catch (StatusRuntimeException e) {
            return ApiResponse.error(4003, "AI Worker 不可用(" + e.getStatus().getCode() + "),请稍后重试");
        }
    }

    private List<String> splitLines(String joined) {
        List<String> out = new java.util.ArrayList<>();
        if (joined == null || joined.isBlank()) {
            return out;
        }
        for (String line : joined.split("\r?\n")) {
            String s = line.trim();
            if (!s.isEmpty()) {
                out.add(s);
            }
        }
        return out;
    }

    private String normalizeJson(String json) {
        if (json == null || json.isBlank()) {
            return null;
        }
        try {
            objectMapper.readTree(json);
            return json;
        } catch (Exception e) {
            throw new IllegalArgumentException("JSON 格式错误: " + e.getMessage());
        }
    }

    private Map<String, Object> parseJson(String json, Map<String, Object> fallback) {
        if (json == null || json.isBlank()) {
            return fallback;
        }
        try {
            return objectMapper.readValue(json,
                    objectMapper.getTypeFactory().constructMapType(LinkedHashMap.class, String.class, Object.class));
        } catch (Exception e) {
            return fallback;
        }
    }

    private String blankToNull(String s) {
        return s == null || s.isBlank() ? null : s;
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
