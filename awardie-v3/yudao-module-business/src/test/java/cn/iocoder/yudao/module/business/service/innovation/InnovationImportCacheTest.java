package cn.iocoder.yudao.module.business.service.innovation;

import org.junit.jupiter.api.Test;

import java.time.Duration;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 批8 导入预览缓存单测
 *
 * <p>这层是"修 v2 伪 sha256 校验"的载体,必须验三件事:
 * token 一次性(消费即失效)、过期即失效、容量有上界(不被畸形文件撑爆内存)。
 *
 * @author AwardIE
 */
class InnovationImportCacheTest {

    private static final Long TENANT = 1L;
    private static final Long OPERATOR = 100L;

    private static InnovationImportService.ImportRow row(int rowNo) {
        return new InnovationImportService.ImportRow(rowNo, "NO-" + rowNo, "项目" + rowNo, "省级",
                "2025-01-01", "2025-12-31", "张三", "212206030", "李四(212206016)", "王五", "2.5", null);
    }

    @Test
    void tokenIsSingleUse() {
        InnovationImportCache cache = new InnovationImportCache(Duration.ofMinutes(30), 20);
        String token = cache.put(List.of(row(2)), TENANT, OPERATOR);

        List<InnovationImportService.ImportRow> first = cache.consume(token, TENANT, OPERATOR);
        assertThat(first).hasSize(1);
        assertThat(first.get(0).projectName()).isEqualTo("项目2");

        // 第二次消费必须拿不到——否则同一个预览点两次会导入两遍
        assertThat(cache.consume(token, TENANT, OPERATOR)).isNull();
    }

    @Test
    void unknownOrNullTokenYieldsNull() {
        InnovationImportCache cache = new InnovationImportCache(Duration.ofMinutes(30), 20);
        assertThat(cache.consume("never-issued", TENANT, OPERATOR)).isNull();
        assertThat(cache.consume(null, TENANT, OPERATOR)).isNull();
        assertThat(cache.consume("  ", TENANT, OPERATOR)).isNull();
    }

    @Test
    void expiredTokenYieldsNull() {
        // TTL 取负:put 时就已过期(取 0 时 expireAt 恰为当下,严格 isBefore 不成立)
        InnovationImportCache cache = new InnovationImportCache(Duration.ofSeconds(-1), 20);
        String token = cache.put(List.of(row(2)), TENANT, OPERATOR);
        assertThat(cache.consume(token, TENANT, OPERATOR)).isNull();
    }

    @Test
    void capacityEvictsOldestInsteadOfGrowing() {
        // 容量 2:放第 3 份时最旧的被挤出
        InnovationImportCache cache = new InnovationImportCache(Duration.ofMinutes(30), 2);
        String first = cache.put(List.of(row(2)), TENANT, OPERATOR);
        String second = cache.put(List.of(row(3)), TENANT, OPERATOR);
        String third = cache.put(List.of(row(4)), TENANT, OPERATOR);

        assertThat(cache.size()).isEqualTo(2);
        assertThat(cache.consume(first, TENANT, OPERATOR)).as("最旧的应被挤出").isNull();
        assertThat(cache.consume(second, TENANT, OPERATOR)).isNotNull();
        assertThat(cache.consume(third, TENANT, OPERATOR)).isNotNull();
    }

    @Test
    void differentTokensHoldDifferentRows() {
        // 防止"所有 token 指向同一份缓存"这种致命 bug
        InnovationImportCache cache = new InnovationImportCache(Duration.ofMinutes(30), 20);
        String a = cache.put(List.of(row(2), row(3)), TENANT, OPERATOR);
        String b = cache.put(List.of(row(4)), TENANT, OPERATOR);

        assertThat(cache.consume(a, TENANT, OPERATOR)).hasSize(2);
        assertThat(cache.consume(b, TENANT, OPERATOR)).hasSize(1);
        assertThat(cache.consume(b, TENANT, OPERATOR)).as("token 一次性").isNull();
    }

}
