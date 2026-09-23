package cn.iocoder.yudao.server.business;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.business.dal.dataobject.laboratory.LaboratoriesDO;
import cn.iocoder.yudao.module.business.dal.mysql.laboratory.LaboratoriesMapper;
import cn.iocoder.yudao.server.YudaoServerApplication;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.MvcResult;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;

/**
 * 批1 首个垂直切片(laboratories)的 API 级测试——v3 集成测试范式样板。
 *
 * 范式约定(后续业务批次照此扩展,测试统一放 yudao-server/src/test/java/cn/iocoder/yudao/server/business/):
 * - @SpringBootTest(classes = YudaoServerApplication.class):全量上下文+完整配置,避开多模块向上搜索问题;
 * - 数据源经 properties 覆盖指向 **awardie_v3_test**(与 dev 库隔离,Q8),口令走环境变量
 *   AWARDIE_MYSQL_PASSWORD(yaml 占位符解析),不入库;
 * - 认证:真实登录换 Bearer token(芋道 token 认证,无 CSRF cookie),租户头 tenant-id: 1;
 *   未登录时芋道返回 **HTTP 200 + body code 401**(业务码式,非 HTTP 401);
 * - 只测外部行为(HTTP 契约 + DB 终态),不测实现细节;种子用 mapper 直插/直清。
 *
 * 与 v2 的语义差(有意保留芋道约定):get 不存在记录时返回 code 0 + data null(v2 为 4004),
 * 删除为逻辑删除(BaseDO @TableLogic,deleted=1)。
 */
@SpringBootTest(classes = YudaoServerApplication.class, properties = {
        // 测试库隔离:指向 awardie_v3_test(用户沿用 local profile 的专用用户,口令走环境变量)
        "spring.datasource.url=jdbc:mysql://127.0.0.1:3307/awardie_v3_test?useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true&nullCatalogMeansCurrent=true&rewriteBatchedStatements=true",
        "spring.datasource.username=awardie_v3"
})
@AutoConfigureMockMvc
class LaboratoriesControllerTest {

    private static final String BASE = "/admin-api/business/laboratories";
    private static final long TENANT_ID = 1L; // 芋道源码默认租户(awardie-cleanup.sql 保留)
    /** 本地/CI 开发环境管理员口令(与 awardie-cleanup.sql 设置一致;生产以部署配置为准) */
    private static final String ADMIN_PASSWORD = "Awardie@V3#2026";

    @Autowired
    private MockMvc mockMvc;
    @Autowired
    private LaboratoriesMapper mapper;

    private final ObjectMapper om = new ObjectMapper();
    private String token;

    @BeforeEach
    void loginAndClean() throws Exception {
        token = loginToken(); // 先登录(HTTP 请求经租户过滤器,结束后会清租户上下文)
        TenantContextHolder.setTenantId(TENANT_ID); // 再设租户上下文,供随后的 mapper 直操使用
        mapper.delete(null); // 清表(逻辑删除:全表 UPDATE deleted=1)
    }

    @AfterEach
    void clearTenant() {
        TenantContextHolder.clear();
    }

    private String loginToken() throws Exception {
        MvcResult result = mockMvc.perform(post("/admin-api/system/auth/login")
                        .contentType(MediaType.APPLICATION_JSON)
                        .header("tenant-id", "1")
                        .content("{\"username\":\"admin\",\"password\":\"" + ADMIN_PASSWORD + "\"}"))
                .andReturn();
        return json(result).path("data").path("accessToken").asText();
    }

    private JsonNode json(MvcResult result) throws Exception {
        return om.readTree(result.getResponse().getContentAsString());
    }

    private HttpHeaders authHeaders() {
        HttpHeaders h = new HttpHeaders();
        h.setBearerAuth(token);
        h.set("tenant-id", "1");
        h.setContentType(MediaType.APPLICATION_JSON);
        return h;
    }

    @Test
    void createGetUpdateDeleteFlow() throws Exception {
        // 创建
        MvcResult created = mockMvc.perform(post(BASE + "/create")
                        .headers(authHeaders())
                        .content("{\"name\":\"测试实验室\",\"description\":\"批1 切片\"}"))
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        long id = json(created).path("data").asLong();

        // 查询:字段与创建值一致
        mockMvc.perform(get(BASE + "/get").headers(authHeaders()).param("id", String.valueOf(id)))
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.name").value("测试实验室"))
                .andExpect(jsonPath("$.data.description").value("批1 切片"));

        // 分页:关键词 LIKE 命中
        mockMvc.perform(get(BASE + "/page").headers(authHeaders())
                        .param("pageNo", "1").param("pageSize", "10").param("name", "测试实验室"))
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.list[0].name").value("测试实验室"));

        // 更新
        mockMvc.perform(put(BASE + "/update").headers(authHeaders())
                        .content("{\"id\":" + id + ",\"name\":\"测试实验室改\",\"description\":\"批1 切片\"}"))
                .andExpect(jsonPath("$.code").value(0));
        mockMvc.perform(get(BASE + "/get").headers(authHeaders()).param("id", String.valueOf(id)))
                .andExpect(jsonPath("$.data.name").value("测试实验室改"));

        // 删除(逻辑删除)后再查:芋道约定返回 code 0 + data null;库中行为 deleted=1
        mockMvc.perform(delete(BASE + "/delete").headers(authHeaders()).param("id", String.valueOf(id)))
                .andExpect(jsonPath("$.code").value(0));
        MvcResult afterDelete = mockMvc.perform(get(BASE + "/get").headers(authHeaders())
                        .param("id", String.valueOf(id)))
                .andExpect(jsonPath("$.code").value(0))
                .andReturn();
        assertThat(json(afterDelete).path("data").isNull()).isTrue();
        // 更新已删记录:业务错误码 1_003_000_000(service 层 validateLaboratoriesExists)
        mockMvc.perform(put(BASE + "/update").headers(authHeaders())
                        .content("{\"id\":" + id + ",\"name\":\"改名再试\",\"description\":\"批1 切片\"}"))
                .andExpect(jsonPath("$.code").value(1003000000));
    }

    @Test
    void pageKeywordMissReturnsEmpty() throws Exception {
        LaboratoriesDO row = new LaboratoriesDO();
        row.setName("关键词未命中实验室");
        mapper.insert(row);
        mockMvc.perform(get(BASE + "/page").headers(authHeaders())
                        .param("pageNo", "1").param("pageSize", "10").param("name", "不存在的关键词"))
                .andExpect(jsonPath("$.code").value(0))
                .andExpect(jsonPath("$.data.list").isEmpty());
    }

    @Test
    void unauthenticatedRejected() throws Exception {
        // 芋道认证失败=HTTP 200 + body code 401(业务码式)
        MvcResult result = mockMvc.perform(get(BASE + "/page")
                        .header("tenant-id", "1").param("pageNo", "1").param("pageSize", "10"))
                .andReturn();
        assertThat(json(result).path("code").asInt()).isEqualTo(401);
    }
}
