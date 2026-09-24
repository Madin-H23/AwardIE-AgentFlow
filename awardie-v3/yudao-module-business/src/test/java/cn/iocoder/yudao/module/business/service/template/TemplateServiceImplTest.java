package cn.iocoder.yudao.module.business.service.template;

import cn.iocoder.yudao.framework.common.exception.ServiceException;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateCreateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateUpdateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesRespVO;
import cn.iocoder.yudao.module.business.dal.dataobject.competition.CompetitionsDO;
import cn.iocoder.yudao.module.business.dal.dataobject.template.TemplatesDO;
import cn.iocoder.yudao.module.business.dal.mysql.competition.CompetitionsMapper;
import cn.iocoder.yudao.module.business.dal.mysql.template.TemplatesMapper;
import cn.iocoder.yudao.module.business.service.file.AwardieFileStorage;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.io.IOException;
import java.lang.reflect.Field;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 批7 模板域服务单测:唯一性、角色白名单、竞赛存在性、编辑白名单、JSON 出入参转换、
 * 规则 JSON 构造、删除时的样本图回收。
 *
 * <p>纯 JUnit + Mockito(不起 Spring、不连库)。夹具用非默认值,避免"因默认值巧合通过"。
 *
 * @author AwardIE
 */
class TemplateServiceImplTest {

    private static final byte[] PNG_BYTES = {(byte) 0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A};
    private static final Long COMP_ID = 42L;
    private static final Long TEMPLATE_ID = 7L;

    private TemplateServiceImpl service;
    private TemplatesMapper templatesMapper;
    private CompetitionsMapper competitionsMapper;
    private AwardieFileStorage fileStorage;

    @BeforeEach
    void setUp() throws Exception {
        service = new TemplateServiceImpl();
        templatesMapper = mock(TemplatesMapper.class);
        competitionsMapper = mock(CompetitionsMapper.class);
        fileStorage = mock(AwardieFileStorage.class);
        inject("templatesMapper", templatesMapper);
        inject("competitionsMapper", competitionsMapper);
        inject("fileStorage", fileStorage);
    }

    private void inject(String field, Object value) throws Exception {
        Field f = TemplateServiceImpl.class.getDeclaredField(field);
        f.setAccessible(true);
        f.set(service, value);
    }

    private void givenCompetitionExists() {
        CompetitionsDO competition = new CompetitionsDO();
        competition.setId(COMP_ID);
        competition.setCompetitionName("测试竞赛");
        when(competitionsMapper.selectById(COMP_ID)).thenReturn(competition);
    }

    private TemplateCreateReqVO validCreateReq() {
        TemplateCreateReqVO req = new TemplateCreateReqVO();
        req.setCompetitionId(COMP_ID);
        req.setGrantedRole("学生");
        req.setKeywords(List.of("一等奖", "  ", "挑战杯"));
        req.setSampleText("样本文本");
        req.setSampleExtracted(Map.of("winner_name", "张三"));
        req.setDefaultFields(Map.of("issued_year", 2024));
        req.setLlmFields(Map.of("fields", List.of("winner_name")));
        req.setLanguage("zh");
        req.setNeedTranslate(false);
        return req;
    }

    // ========== 创建 ==========

    @Test
    void createStoresStructuredJsonAndDerivedFields() throws IOException {
        givenCompetitionExists();
        when(templatesMapper.selectCountByCompetitionAndRole(eq(COMP_ID), eq("学生"), any())).thenReturn(0L);
        when(fileStorage.store(anyString(), any())).thenReturn(
                new AwardieFileStorage.StoredFile("abc123.png", "hashvalue", PNG_BYTES.length));
        // 真实 MyBatis insert 会回填自增主键,mock 不会,这里手动模拟该副作用
        org.mockito.Mockito.doAnswer(invocation -> {
            invocation.getArgument(0, TemplatesDO.class).setId(TEMPLATE_ID);
            return 1;
        }).when(templatesMapper).insert(any(TemplatesDO.class));

        Long id = service.createTemplate(validCreateReq(), "sample.png", PNG_BYTES);

        assertThat(id).isNotNull();
        ArgumentCaptor<TemplatesDO> captor = ArgumentCaptor.forClass(TemplatesDO.class);
        verify(templatesMapper).insert(captor.capture());
        TemplatesDO saved = captor.getValue();
        // 类型固定 AWARD(v2 语义)
        assertThat(saved.getTemplateType()).isEqualTo("AWARD");
        // granted_role 落在独立列(不是 JSON 里)
        assertThat(saved.getGrantedRole()).isEqualTo("学生");
        // 关键词清洗:去空白项 + trim,存 JSON 数组字符串
        assertThat(saved.getKeywords()).isEqualTo("[\"一等奖\",\"挑战杯\"]");
        // 结构化对象序列化为 JSON
        assertThat(saved.getSampleExtracted()).contains("张三");
        assertThat(saved.getDefaultFields()).contains("2024");
        assertThat(saved.getSampleImagePath()).isEqualTo("abc123.png");
    }

    @Test
    void createRejectsInvalidRole() throws IOException {
        givenCompetitionExists();
        TemplateCreateReqVO req = validCreateReq();
        req.setGrantedRole("教师2"); // 非枚举值
        assertThatThrownBy(() -> service.createTemplate(req, "s.png", PNG_BYTES))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("学生或教师");
        // 角色非法应在落盘前就拒
        verify(fileStorage, never()).store(anyString(), any());
    }

    @Test
    void createRejectsUnknownCompetition() throws IOException {
        when(competitionsMapper.selectById(COMP_ID)).thenReturn(null);
        assertThatThrownBy(() -> service.createTemplate(validCreateReq(), "s.png", PNG_BYTES))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("竞赛不存在");
        verify(fileStorage, never()).store(anyString(), any());
    }

    @Test
    void createRejectsDuplicateRoleForSameCompetition() throws IOException {
        givenCompetitionExists();
        // 同竞赛同角色已有模板
        when(templatesMapper.selectCountByCompetitionAndRole(eq(COMP_ID), eq("学生"), any())).thenReturn(1L);
        assertThatThrownBy(() -> service.createTemplate(validCreateReq(), "s.png", PNG_BYTES))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("已存在模板");
        verify(fileStorage, never()).store(anyString(), any());
    }

    // ========== 编辑 ==========

    @Test
    void updateOnlyTouchesWhitelistedFields() {
        TemplatesDO existing = new TemplatesDO();
        existing.setId(TEMPLATE_ID);
        existing.setCompetitionId(COMP_ID);
        existing.setGrantedRole("教师");
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(existing);

        TemplateUpdateReqVO req = new TemplateUpdateReqVO();
        req.setKeywords(List.of("新关键词"));
        req.setMinLength(5);
        req.setMaxLength(100);
        service.updateTemplate(TEMPLATE_ID, req);

        ArgumentCaptor<TemplatesDO> captor = ArgumentCaptor.forClass(TemplatesDO.class);
        verify(templatesMapper).updateById(captor.capture());
        TemplatesDO update = captor.getValue();
        assertThat(update.getId()).isEqualTo(TEMPLATE_ID);
        assertThat(update.getKeywords()).isEqualTo("[\"新关键词\"]");
        assertThat(update.getMinLength()).isEqualTo(5);
        // 白名单外字段绝不出现在更新对象里(grantedRole/competitionId 不可被改)
        assertThat(update.getGrantedRole()).isNull();
        assertThat(update.getCompetitionId()).isNull();
        assertThat(update.getSampleImagePath()).isNull();
    }

    @Test
    void updateMissingTemplateReportsNotExists() {
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(null);
        assertThatThrownBy(() -> service.updateTemplate(TEMPLATE_ID, new TemplateUpdateReqVO()))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("证书模板不存在");
    }

    // ========== 删除 ==========

    @Test
    void deleteReclaimsSampleImageWhenUnreferenced() throws IOException {
        TemplatesDO existing = new TemplatesDO();
        existing.setId(TEMPLATE_ID);
        existing.setSampleImagePath("abc.png");
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(existing);

        service.deleteTemplate(TEMPLATE_ID);

        verify(templatesMapper).deleteById(TEMPLATE_ID);
        // 回收走"删前查引用",不是无条件删
        verify(fileStorage).deleteIfUnreferenced("abc.png");
    }

    @Test
    void deleteSurvivesIoFailureOnReclaim() throws IOException {
        TemplatesDO existing = new TemplatesDO();
        existing.setId(TEMPLATE_ID);
        existing.setSampleImagePath("abc.png");
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(existing);
        org.mockito.Mockito.doThrow(new IOException("disk error")).when(fileStorage).deleteIfUnreferenced(anyString());

        // 物理文件回收失败不应让业务删除失败(记录已是逻辑删除态)
        service.deleteTemplate(TEMPLATE_ID);
        verify(templatesMapper).deleteById(TEMPLATE_ID);
    }

    // ========== 详情与规则 JSON ==========

    @Test
    void getTemplateReturnsStructuredFieldsAndHasImage() {
        givenCompetitionExists();
        TemplatesDO entity = new TemplatesDO();
        entity.setId(TEMPLATE_ID);
        entity.setCompetitionId(COMP_ID);
        entity.setGrantedRole("学生");
        entity.setKeywords("[\"奖状\"]");
        entity.setSampleExtracted("{\"winner_name\":\"李四\"}");
        entity.setSampleImagePath("img.png");
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(entity);

        TemplatesRespVO vo = service.getTemplate(TEMPLATE_ID);
        assertThat(vo.getKeywords()).containsExactly("奖状");
        assertThat(vo.getSampleExtracted()).containsEntry("winner_name", "李四");
        assertThat(vo.getHasImage()).isTrue();
        assertThat(vo.getCompetitionName()).isEqualTo("测试竞赛");
    }

    @Test
    void getTemplateReportsHasImageFalseWhenNoPath() {
        givenCompetitionExists();
        TemplatesDO entity = new TemplatesDO();
        entity.setId(TEMPLATE_ID);
        entity.setCompetitionId(COMP_ID);
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(entity);
        assertThat(service.getTemplate(TEMPLATE_ID).getHasImage()).isFalse();
    }

    @Test
    void buildRuleJsonIncludesAllRuleFieldsWithDefaults() {
        TemplatesDO entity = new TemplatesDO();
        entity.setKeywords("[\"奖状\",\"一等奖\"]");
        entity.setSampleExtracted("{\"winner_name\":\"王五\"}");
        entity.setDefaultFields("{\"issued_year\":2024}");
        entity.setLlmFields("{\"fields\":[\"winner_name\"]}");
        // min/max/language/needTranslate 全空 → 应落到默认 0/zh/false
        String ruleJson = service.buildRuleJson(entity);
        assertThat(ruleJson).contains("\"keywords\":[\"奖状\",\"一等奖\"]");
        assertThat(ruleJson).contains("\"winner_name\"");
        assertThat(ruleJson).contains("\"min_length\":0");
        assertThat(ruleJson).contains("\"max_length\":0");
        assertThat(ruleJson).contains("\"language\":\"zh\"");
        assertThat(ruleJson).contains("\"need_translate\":false");
    }

    @Test
    void buildRuleJsonToleratesCorruptedStoredJson() {
        // 库里存的是本服务序列化的 JSON,但历史脏数据不应让规则构造炸掉
        TemplatesDO entity = new TemplatesDO();
        entity.setKeywords("{broken");
        entity.setSampleExtracted("{broken");
        String ruleJson = service.buildRuleJson(entity);
        assertThat(ruleJson).contains("\"keywords\":[]");
    }

    // ========== 样本图读取 ==========

    @Test
    void getSampleImageRejectsTemplateWithoutImage() throws IOException {
        TemplatesDO entity = new TemplatesDO();
        entity.setId(TEMPLATE_ID);
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(entity);
        assertThatThrownBy(() -> service.getSampleImage(TEMPLATE_ID))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("没有样本图片");
    }

    @Test
    void getSampleImageReportsLostFile() throws IOException {
        TemplatesDO entity = new TemplatesDO();
        entity.setId(TEMPLATE_ID);
        entity.setSampleImagePath("gone.png");
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(entity);
        when(fileStorage.readAll("gone.png")).thenThrow(new java.nio.file.NoSuchFileException("gone.png"));
        assertThatThrownBy(() -> service.getSampleImage(TEMPLATE_ID))
                .isInstanceOf(ServiceException.class)
                .hasMessageContaining("样本图文件缺失");
    }

    @Test
    void getSampleImageReturnsBytes() throws IOException {
        TemplatesDO entity = new TemplatesDO();
        entity.setId(TEMPLATE_ID);
        entity.setSampleImagePath("img.png");
        when(templatesMapper.selectById(TEMPLATE_ID)).thenReturn(entity);
        when(fileStorage.readAll("img.png")).thenReturn(PNG_BYTES);
        assertThat(service.getSampleImage(TEMPLATE_ID)).isEqualTo(PNG_BYTES);
    }

}
