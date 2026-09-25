package cn.iocoder.yudao.module.business.service.innovation;

import cn.hutool.core.util.StrUtil;
import cn.iocoder.yudao.module.business.dal.dataobject.innovation.InnovationProjectStudentDO;
import cn.iocoder.yudao.module.business.dal.mysql.innovation.InnovationProjectStudentMapper;
import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.mysql.user.AdminUserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import jakarta.annotation.Resource;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.stereotype.Component;
import org.springframework.validation.annotation.Validated;

/**
 * 大创学生关联匹配器(批8,决策 B-lite + V1 数据为准)
 *
 * <p>为什么需要(本机 V1 SQLite + V2 PostgreSQL 双库实测):两库的
 * `innovation_project_students` 都有真实数据(V1 20 个项目、V2 28 行覆盖全部 20 个项目),
 * `match_type` 全是 `student_id_exact`,且学生门户"我的大创"**只查这张表**
 * ——它是学生看到自己项目的唯一途径。但两侧 Java 代码都只有 SELECT 没有 INSERT,
 * 这些行是一次性脚本灌的,导致**导入的新项目学生端永远看不到**。这是缺陷不是语义,本批修掉。
 *
 * <p>成员格式以 V1 为准:实测 V1 库的 `other_members` 存的是
 * {@code [{"姓名":"江圣","学号":"212206016"}, ...]} 结构化对象数组;V1 代码另兼容
 * 旧格式 {@code "张三(2022001)"} 字符串数组与逗号分隔纯姓名。本实现三种都认,
 * 优先取学号——**只有姓名无法可靠匹配(重名会错配),宁可跳过并计入未匹配**。
 *
 * <p>学号存在哪:v3 的 `system_users.username` 就是学号——批2 ETL 把 v2 `login_code`
 * 映射过来(实测 1792 个纯数字账号),不需要新增字段。
 *
 * @author AwardIE
 */
@Component
@Validated
@Slf4j
public class InnovationStudentMatcher {

    /**
     * 学号形态:8-20 位纯数字
     *
     * <p>下限取 8 是实测结论:V1/V2 两库的 `student_id_str` 长度**全为 9**
     * (212206030 这类)。下限放到 6 会把 6-7 位的短数字也当学号,徒增误匹配面。
     */
    private static final int MIN_ID_LENGTH = 8;
    private static final int MAX_ID_LENGTH = 20;

    @Resource
    private AdminUserMapper userMapper;
    @Resource
    private InnovationProjectStudentMapper studentMapper;

    /**
     * 为一个导入的项目建立学生关联
     *
     * @param row       导入行(取负责人学号与其他成员)
     * @param projectId 项目编号
     * @param tenantId  租户编号
     * @return 关联结果(成功数 / 未匹配数)
     */
    public LinkOutcome linkStudents(InnovationImportService.ImportRow row, Long projectId, Long tenantId) {
        int linked = 0;
        int unmatched = 0;
        // leader:学号精确匹配
        if (isStudentId(row.leaderId())) {
            if (linkOne(projectId, tenantId, row.leaderId(), row.leaderName(),
                    InnovationProjectStudentDO.ROLE_LEADER)) {
                linked++;
            } else {
                unmatched++;
            }
        }
        // member:其他成员里能解析出学号的项(V1 三种格式都认)
        for (MemberRef ref : StudentMembers.parseMembers(row.otherMembers())) {
            if (!isStudentId(ref.studentId())) {
                // 纯姓名项:本就没有学号,无法可靠匹配(重名会错配),不计未匹配
                continue;
            }
            if (linkOne(projectId, tenantId, ref.studentId(), ref.name(),
                    InnovationProjectStudentDO.ROLE_MEMBER)) {
                linked++;
            } else {
                unmatched++;
            }
        }
        return new LinkOutcome(linked, unmatched);
    }

    /**
     * 关联结果
     *
     * @param linked    成功建立的关联数
     * @param unmatched 提供了学号但查无此人的数量
     */
    public record LinkOutcome(int linked, int unmatched) {
    }

    /**
     * 建立单条关联(匹配上才建)
     *
     * @return true=建立成功;false=学号查无此人或重复
     */
    private boolean linkOne(Long projectId, Long tenantId, String studentId, String nameHint, String role) {
        AdminUserDO user = userMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getUsername, studentId));
        if (user == null) {
            // 不阻断:学号查无此人可能是学生还没建账号,导入仍应成功
            log.debug("[innovation-match] 项目 {} 的 {} 学号 {} 未匹配到用户", projectId, role, studentId);
            return false;
        }
        InnovationProjectStudentDO entity = new InnovationProjectStudentDO();
        entity.setProjectId(projectId);
        entity.setStudentId(user.getId());
        entity.setRole(role);
        entity.setStudentName(StrUtil.blankToDefault(nameHint, user.getNickname()));
        entity.setStudentIdStr(studentId);
        entity.setMatchType(InnovationProjectStudentDO.MATCH_STUDENT_ID_EXACT);
        entity.setTenantId(tenantId);
        try {
            studentMapper.insert(entity);
        } catch (DuplicateKeyException e) {
            // 同一学生既是 leader 又出现在成员列:唯一键 (project_id, student_id, deleted) 挡住
            return false;
        }
        return true;
    }

    /**
     * 判断字符串是否像学号(纯数字且长度合理)
     *
     * <p>用于区分"其他成员"里的学号项与纯姓名项——姓名不该拿去匹配用户,
     * 强行按姓名匹配会因重名错配,比不匹配更糟。
     *
     * @param value 候选值
     * @return true=形如学号
     */
    public static boolean isStudentId(String value) {
        if (StrUtil.isBlank(value)) {
            return false;
        }
        String trimmed = value.trim();
        if (trimmed.length() < MIN_ID_LENGTH || trimmed.length() > MAX_ID_LENGTH) {
            return false;
        }
        return trimmed.chars().allMatch(Character::isDigit);
    }

    /**
     * 解析出的成员引用
     *
     * @param name      姓名(可能为空)
     * @param studentId 学号(可能为空——纯姓名项)
     */
    public record MemberRef(String name, String studentId) {
    }

}
