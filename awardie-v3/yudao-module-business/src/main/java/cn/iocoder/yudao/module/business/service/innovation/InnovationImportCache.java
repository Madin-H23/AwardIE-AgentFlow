package cn.iocoder.yudao.module.business.service.innovation;

import org.springframework.stereotype.Component;

import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * 大创导入预览缓存(批8)
 *
 * <p>存在的理由:修 v2 的"伪 sha256 校验"缺陷。v2 的 preview 返回文件哈希,
 * confirm 也接收它,但 controller 与 service 都不用——不缓存 preview、不验证
 * 客户端回传的行是否真来自那个文件,测试里传字符串 "x" 照样成功。
 * 后果是 confirm **完全信任客户端提交的 rows**,可以往库里写任意内容。
 *
 * <p>本实现:preview 把解析结果存服务端,返回随机 token;confirm **只接受 token**,
 * 行数据一律从缓存取,客户端篡改请求体没有任何效果。token 消费即失效。
 *
 * <p><b>条目绑定租户与操作人</b>(security-audit H-1):否则租户 A 的 token 泄露后,
 * 租户 B 的管理员可拿它 confirm,把 A 的项目内容写进 B 的库并读到 A 的项目名/成员/学号。
 * confirm 时校验绑定主体,不匹配即视为无效 token。
 *
 * <p><b>并发安全</b>(security-audit M-5):Spring 单例被多请求并发访问,
 * 普通 LinkedHashMap 会让"token 一次性"在并发下失效(两个请求可能同时取到同一 Entry),
 * 且容量淘汰不是原子操作。本类所有公开方法加 synchronized——导入是低频管理操作,
 * 锁竞争可忽略,换来的是语义正确。
 *
 * <p>过期与容量:默认 30 分钟过期、最多 20 份。过期或被挤出即视为失效,需重新上传。
 * 服务重启后缓存丢失属可接受(单实例部署下影响是"重新上传一次")。
 *
 * <p>已知边界:内存缓存,<b>多实例部署时 confirm 可能打到另一实例找不到 token</b>。
 * 生产若多实例,需换共享缓存(Redis)。已记入部署清单。
 *
 * @author AwardIE
 */
@Component
public class InnovationImportCache {

    /** 预览有效期:30 分钟(用户核对预览再确认的合理时长) */
    public static final Duration DEFAULT_TTL = Duration.ofMinutes(30);
    /** 最多保留的预览份数(超出淘汰最旧的) */
    public static final int DEFAULT_MAX_ENTRIES = 20;

    private final Map<String, Entry> entries = new LinkedHashMap<>();
    private final Duration ttl;
    private final int maxEntries;

    public InnovationImportCache() {
        this(DEFAULT_TTL, DEFAULT_MAX_ENTRIES);
    }

    public InnovationImportCache(Duration ttl, int maxEntries) {
        this.ttl = ttl;
        this.maxEntries = maxEntries;
    }

    /**
     * 保存预览结果
     *
     * @param rows       已解析并逐行校验的行
     * @param tenantId   租户编号(绑定主体,confirm 时校验)
     * @param operatorId 操作人编号(绑定主体,confirm 时校验)
     * @return token(confirm 时凭此取回行数据)
     */
    public synchronized String put(List<InnovationImportService.ImportRow> rows, Long tenantId, Long operatorId) {
        purgeExpired();
        while (entries.size() >= maxEntries) {
            var oldest = entries.keySet().iterator().next();
            entries.remove(oldest);
        }
        String token = UUID.randomUUID().toString();
        entries.put(token, new Entry(rows, tenantId, operatorId, Instant.now().plus(ttl)));
        return token;
    }

    /**
     * 取出并消费预览(token 一次性 + 主体绑定校验)
     *
     * @param token      预览令牌
     * @param tenantId   当前租户
     * @param operatorId 当前操作人
     * @return 行数据;token 不存在/已过期/已使用/主体不匹配一律返回 null
     */
    public synchronized List<InnovationImportService.ImportRow> consume(String token, Long tenantId,
            Long operatorId) {
        if (token == null || token.isBlank()) {
            return null;
        }
        Entry entry = entries.remove(token);
        if (entry == null || entry.expireAt().isBefore(Instant.now())) {
            return null;
        }
        // 主体不匹配:当作无效 token(不泄露"该 token 存在但不属于你")
        if (!java.util.Objects.equals(entry.tenantId(), tenantId)
                || !java.util.Objects.equals(entry.operatorId(), operatorId)) {
            return null;
        }
        return entry.rows();
    }

    private void purgeExpired() {
        Instant now = Instant.now();
        List<String> expired = new ArrayList<>();
        entries.forEach((k, v) -> {
            if (v.expireAt().isBefore(now)) {
                expired.add(k);
            }
        });
        expired.forEach(entries::remove);
    }

    /** 当前缓存份数(测试与运维观测用) */
    public synchronized int size() {
        return entries.size();
    }

    private record Entry(List<InnovationImportService.ImportRow> rows, Long tenantId, Long operatorId,
                         Instant expireAt) {
    }

}
