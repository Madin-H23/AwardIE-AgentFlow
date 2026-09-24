package cn.iocoder.yudao.module.business.service.template;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateCreateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateUpdateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesRespVO;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.dal.dataobject.template.TemplatesDO;
import cn.iocoder.yudao.module.business.dal.mysql.competition.CompetitionsMapper;
import cn.iocoder.yudao.module.business.dal.mysql.template.TemplatesMapper;
import cn.iocoder.yudao.module.business.service.file.AwardieFileStorage;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;
import org.springframework.validation.annotation.Validated;

import java.io.IOException;
import java.nio.file.NoSuchFileException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import static cn.iocoder.yudao.framework.common.exception.util.ServiceExceptionUtil.exception;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.COMPETITIONS_NOT_EXISTS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_DUPLICATE_ROLE;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_JSON_INVALID;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_NOT_EXISTS;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_ROLE_INVALID;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_RULE_INVALID;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_SAMPLE_IMAGE_LOST;
import static cn.iocoder.yudao.module.business.enums.ErrorCodeConstants.TEMPLATE_SAMPLE_IMAGE_MISSING;

/**
 * AwardIE 证书模板 Service 实现(批7)
 *
 * <p>相对 v2 的三处关键差异(详见 docs 批7 01-spec 决策表):
 * <ol>
 *   <li>有分层(v2 的 SQL 全写在 Controller 里);</li>
 *   <li>granted_role 独立列 + 编辑不可改(v2 改 default_fields 即可绕过唯一性);</li>
 *   <li>JSON 字段出入参为结构化对象(v2 存 JSON 字符串、前后端契约错位)。</li>
 * </ol>
 *
 * @author AwardIE
 */
@Service
@Validated
@Slf4j
public class TemplateServiceImpl implements TemplateService {

    /** 授予角色白名单(v2 硬判"学生"/"教师") */
    public static final Set<String> GRANTED_ROLES = Set.of("学生", "教师");
    /** 模板类型:本域只做奖状(v2 template_type 恒 'AWARD') */
    private static final String TEMPLATE_TYPE_AWARD = "AWARD";
    /** 默认语言(v2 空值回退 zh) */
    private static final String DEFAULT_LANGUAGE = "zh";
    /** defaultFields 里的保留键:授予角色以独立列为唯一事实源,不允许在 JSON 里重复表达 */
    private static final String RESERVED_ROLE_KEY = "granted_role";

    private static final ObjectMapper MAPPER = new ObjectMapper();

    @Resource
    private TemplatesMapper templatesMapper;
    @Resource
    private CompetitionsMapper competitionsMapper;
    @Resource
    private AwardieFileStorage fileStorage;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Long createTemplate(TemplateCreateReqVO createReqVO, String filename, byte[] fileBytes)
            throws IOException {
        validateRole(createReqVO.getGrantedRole());
        validateCompetitionExists(createReqVO.getCompetitionId());
        validateLengths(createReqVO.getMinLength(), createReqVO.getMaxLength());
        validateRoleUnique(createReqVO.getCompetitionId(), createReqVO.getGrantedRole(), null);
        // 样本图先过三校验再落盘(v2 同序:扩展名 → 大小 → 魔术字节)
        fileStorage.assertAllowed(filename, fileBytes);
        // 规则字段先序列化成功再落盘:序列化在内存里,失败不留孤儿文件
        String keywordsJson = writeKeywords(createReqVO.getKeywords());
        String sampleExtractedJson = writeObject(createReqVO.getSampleExtracted());
        String defaultFieldsJson = writeObject(withoutReservedRole(createReqVO.getDefaultFields()));
        String llmFieldsJson = writeObject(createReqVO.getLlmFields());

        AwardieFileStorage.StoredFile stored = fileStorage.store(filename, fileBytes);
        // 立刻注册回滚补偿:insert 失败时样本图不能变孤儿(批7)
        registerFileCompensation(stored.relativePath(), false);

        TemplatesDO entity = new TemplatesDO();
        entity.setTemplateType(TEMPLATE_TYPE_AWARD);
        entity.setCompetitionId(createReqVO.getCompetitionId());
        entity.setGrantedRole(createReqVO.getGrantedRole());
        entity.setMinLength(orZero(createReqVO.getMinLength()));
        entity.setMaxLength(orZero(createReqVO.getMaxLength()));
        entity.setKeywords(keywordsJson);
        entity.setSampleText(createReqVO.getSampleText());
        entity.setSampleExtracted(sampleExtractedJson);
        entity.setDefaultFields(defaultFieldsJson);
        entity.setLlmFields(llmFieldsJson);
        entity.setLanguage(blankToDefault(createReqVO.getLanguage()));
        entity.setNeedTranslate(Boolean.TRUE.equals(createReqVO.getNeedTranslate()));
        entity.setSampleImagePath(stored.relativePath());
        templatesMapper.insert(entity);
        return entity.getId();
    }

    @Override
    public void updateTemplate(Long id, TemplateUpdateReqVO updateReqVO) {
        TemplatesDO existing = getTemplateDO(id);
        validateLengths(updateReqVO.getMinLength(), updateReqVO.getMaxLength());
        // 编辑白名单:只改规则字段。grantedRole/competitionId 不在 UpdateReqVO 里,
        // v2 可通过改 defaultFields 绕过唯一性,本批明确堵掉
        TemplatesDO updateObj = new TemplatesDO();
        updateObj.setId(existing.getId());
        updateObj.setMinLength(orZero(updateReqVO.getMinLength()));
        updateObj.setMaxLength(orZero(updateReqVO.getMaxLength()));
        updateObj.setKeywords(writeKeywords(updateReqVO.getKeywords()));
        updateObj.setSampleText(updateReqVO.getSampleText());
        updateObj.setSampleExtracted(writeObject(updateReqVO.getSampleExtracted()));
        updateObj.setDefaultFields(writeObject(withoutReservedRole(updateReqVO.getDefaultFields())));
        updateObj.setLlmFields(writeObject(updateReqVO.getLlmFields()));
        updateObj.setLanguage(blankToDefault(updateReqVO.getLanguage()));
        updateObj.setNeedTranslate(Boolean.TRUE.equals(updateReqVO.getNeedTranslate()));
        templatesMapper.updateById(updateObj);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteTemplate(Long id) {
        TemplatesDO existing = getTemplateDO(id);
        // 逻辑删除(v3 基座口径);模板无下游业务引用,故不做引用拒绝
        templatesMapper.deleteById(id);
        if (existing.getSampleImagePath() != null) {
            // 物理文件回收必须等事务**提交成功**后:若在事务内就删,而 commit 阶段失败,
            // 库行会回滚成"模板仍有效"但样本图已被删,留下损坏状态。
            registerFileCompensation(existing.getSampleImagePath(), true);
        }
    }

    /**
     * 注册文件补偿钩子
     *
     * @param relativePath 相对存储根的路径
     * @param onCommit     true=提交成功后回收(删除模板场景);
     *                    false=回滚时回收(创建失败场景)
     */
    private void registerFileCompensation(String relativePath, boolean onCommit) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            // 无事务上下文:直接执行(退化为无补偿保护,不应发生)
            if (onCommit) {
                reclaimQuietly(relativePath);
            }
            return;
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCompletion(int status) {
                // 只认明确的两种终态。STATUS_UNKNOWN 表示结果未知(commit 时连接中断),
                // 此时库行可能已落库,删文件会打断它 —— 保留待巡检清理。
                if (onCommit) {
                    if (status == TransactionSynchronization.STATUS_COMMITTED) {
                        reclaimQuietly(relativePath);
                    } else if (status == TransactionSynchronization.STATUS_UNKNOWN) {
                        log.warn("[template] 事务结果未知,保留样本图待巡检清理: {}", relativePath);
                    }
                } else if (status == TransactionSynchronization.STATUS_ROLLED_BACK) {
                    reclaimQuietly(relativePath);
                } else if (status == TransactionSynchronization.STATUS_UNKNOWN) {
                    log.warn("[template] 事务结果未知,保留样本图待巡检清理: {}", relativePath);
                }
            }
        });
    }

    /** 回收样本图:失败只记 warn,不影响已提交的业务结果(残留只是占空间) */
    private void reclaimQuietly(String relativePath) {
        try {
            fileStorage.deleteIfUnreferenced(relativePath);
        } catch (Exception e) {
            log.warn("[template] 样本图回收失败,可能残留文件: {}", relativePath, e);
        }
    }

    @Override
    public TemplatesRespVO getTemplate(Long id) {
        TemplatesDO entity = getTemplateDO(id);
        return toRespVO(entity, competitionNameOf(entity.getCompetitionId()));
    }

    @Override
    public byte[] getSampleImage(Long id) throws IOException {
        TemplatesDO entity = getTemplateDO(id);
        if (entity.getSampleImagePath() == null || entity.getSampleImagePath().isBlank()) {
            throw exception(TEMPLATE_SAMPLE_IMAGE_MISSING);
        }
        try {
            return fileStorage.readAll(entity.getSampleImagePath());
        } catch (NoSuchFileException e) {
            // 存量死引用(物理文件被外部清理):明确报错而非 500
            throw exception(TEMPLATE_SAMPLE_IMAGE_LOST);
        }
    }

    @Override
    public String getSampleImageContentType(Long id) {
        return fileStorage.contentTypeOf(getTemplateDO(id).getSampleImagePath());
    }

    @Override
    public PageResult<TemplatesRespVO> getTemplatePage(TemplatesPageReqVO pageReqVO) {
        PageResult<TemplatesDO> pageResult = templatesMapper.selectPage(pageReqVO);
        List<TemplatesRespVO> list = new ArrayList<>(pageResult.getList().size());
        for (TemplatesDO entity : pageResult.getList()) {
            list.add(toRespVO(entity, competitionNameOf(entity.getCompetitionId())));
        }
        return new PageResult<>(list, pageResult.getTotal());
    }

    @Override
    public TemplatesDO getTemplateDO(Long id) {
        TemplatesDO entity = templatesMapper.selectById(id);
        if (entity == null) {
            throw exception(TEMPLATE_NOT_EXISTS);
        }
        return entity;
    }

    @Override
    public String buildRuleJson(TemplatesDO template) {
        Map<String, Object> rule = new LinkedHashMap<>();
        rule.put("keywords", readArray(template.getKeywords()));
        rule.put("sample_extracted", readObject(template.getSampleExtracted()));
        rule.put("default_fields", readObject(template.getDefaultFields()));
        rule.put("llm_fields", readObject(template.getLlmFields()));
        rule.put("min_length", orZero(template.getMinLength()));
        rule.put("max_length", orZero(template.getMaxLength()));
        rule.put("language", blankToDefault(template.getLanguage()));
        rule.put("need_translate", Boolean.TRUE.equals(template.getNeedTranslate()));
        try {
            return MAPPER.writeValueAsString(rule);
        } catch (Exception e) {
            // 库里存的是本服务自己序列化过的 JSON,序列化失败说明数据已损坏
            return "{}";
        }
    }

    // ========== 校验 ==========

    private void validateRole(String grantedRole) {
        // Set.of().contains(null) 抛 NPE(不可变集合不接受 null 查询),显式判空给出业务错误
        if (grantedRole == null || !GRANTED_ROLES.contains(grantedRole)) {
            throw exception(TEMPLATE_ROLE_INVALID);
        }
    }

    /** 长度区间:非负且 min ≤ max(0 = 不限,v2 语义);反区间会让下游 prompt 拼接产出空约束 */
    private void validateLengths(Integer minLength, Integer maxLength) {
        if (minLength != null && minLength < 0) {
            throw exception(TEMPLATE_RULE_INVALID, "min_length 不能为负");
        }
        if (maxLength != null && maxLength < 0) {
            throw exception(TEMPLATE_RULE_INVALID, "max_length 不能为负");
        }
        if (minLength != null && maxLength != null && minLength > 0 && maxLength > 0
                && minLength > maxLength) {
            throw exception(TEMPLATE_RULE_INVALID, "min_length 不能大于 max_length");
        }
    }

    private void validateCompetitionExists(Long competitionId) {
        CompetitionsDO competition = competitionId == null ? null
                : competitionsMapper.selectById(competitionId);
        if (competition == null) {
            throw exception(COMPETITIONS_NOT_EXISTS);
        }
    }

    /** 同竞赛 + 同授予角色 + 未删除 只允许一个模板(不加 DB 唯一索引:逻辑删除下会误伤已删行) */
    private void validateRoleUnique(Long competitionId, String grantedRole, Long excludeId) {
        Long count = templatesMapper.selectCountByCompetitionAndRole(competitionId, grantedRole, excludeId);
        if (count != null && count > 0) {
            throw exception(TEMPLATE_DUPLICATE_ROLE);
        }
    }

    // ========== 转换 ==========

    private TemplatesRespVO toRespVO(TemplatesDO entity, String competitionName) {
        TemplatesRespVO vo = new TemplatesRespVO();
        vo.setId(entity.getId());
        vo.setTemplateType(entity.getTemplateType());
        vo.setCompetitionId(entity.getCompetitionId());
        vo.setCompetitionName(competitionName);
        vo.setGrantedRole(entity.getGrantedRole());
        vo.setMinLength(orZero(entity.getMinLength()));
        vo.setMaxLength(orZero(entity.getMaxLength()));
        vo.setKeywords(readArray(entity.getKeywords()));
        vo.setSampleText(entity.getSampleText());
        vo.setSampleExtracted(readObject(entity.getSampleExtracted()));
        vo.setDefaultFields(readObject(entity.getDefaultFields()));
        vo.setLlmFields(readObject(entity.getLlmFields()));
        vo.setLanguage(blankToDefault(entity.getLanguage()));
        vo.setNeedTranslate(Boolean.TRUE.equals(entity.getNeedTranslate()));
        vo.setHasImage(entity.getSampleImagePath() != null && !entity.getSampleImagePath().isBlank());
        vo.setCreateTime(entity.getCreateTime());
        return vo;
    }

    private String competitionNameOf(Long competitionId) {
        CompetitionsDO competition = competitionId == null ? null
                : competitionsMapper.selectById(competitionId);
        return competition == null ? null : competition.getCompetitionName();
    }

    private static String writeKeywords(List<String> keywords) {
        if (keywords == null) {
            return "[]";
        }
        List<String> cleaned = keywords.stream()
                .filter(k -> k != null && !k.isBlank())
                .map(String::trim)
                .toList();
        try {
            return MAPPER.writeValueAsString(cleaned);
        } catch (Exception e) {
            // 序列化成字符串数组理论上不会失败,但不能静默变空数组:那会让用户的规则
            // 无声消失还看不出错。失败必须显式暴露。
            throw exception(TEMPLATE_JSON_INVALID, e.getMessage());
        }
    }

    private static String writeObject(Map<String, Object> value) {
        if (value == null) {
            return null;
        }
        try {
            return MAPPER.writeValueAsString(value);
        } catch (Exception e) {
            // 同样不能静默写 null:库里会出现"字段为空"而不是"保存失败",难以排查
            throw exception(TEMPLATE_JSON_INVALID, e.getMessage());
        }
    }

    /**
     * 剔除 defaultFields 里的保留键 granted_role
     *
     * <p>v2 把授予角色藏在 default_fields 里,编辑时可改它绕过唯一性。v3 已把角色提为
     * 独立列,若仍允许在 defaultFields 里写同名字段,库里就会出现两套可能互相矛盾的角色表示,
     * 未来任何读 defaultFields 的消费者都可能取到过期值。独立列是唯一事实源。
     */
    private static Map<String, Object> withoutReservedRole(Map<String, Object> value) {
        if (value == null || !value.containsKey(RESERVED_ROLE_KEY)) {
            return value;
        }
        Map<String, Object> copy = new LinkedHashMap<>(value);
        copy.remove(RESERVED_ROLE_KEY);
        return copy;
    }

    private static List<String> readArray(String json) {
        if (json == null || json.isBlank()) {
            return List.of();
        }
        try {
            return MAPPER.readValue(json, new TypeReference<List<String>>() {
            });
        } catch (Exception e) {
            return List.of();
        }
    }

    private static Map<String, Object> readObject(String json) {
        if (json == null || json.isBlank()) {
            return Map.of();
        }
        try {
            return MAPPER.readValue(json, new TypeReference<Map<String, Object>>() {
            });
        } catch (Exception e) {
            return Map.of();
        }
    }

    private static int orZero(Integer value) {
        return value == null ? 0 : value;
    }

    private static String blankToDefault(String language) {
        return language == null || language.isBlank() ? DEFAULT_LANGUAGE : language;
    }

}
