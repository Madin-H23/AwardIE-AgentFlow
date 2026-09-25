package cn.iocoder.yudao.module.business.service.innovation;

import cn.iocoder.yudao.module.business.service.innovation.InnovationStudentMatcher.MemberRef;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * 批8 其他成员解析与序列化单测(以 V1 数据为准)
 *
 * <p>V1 库实测格式是 {@code [{"姓名":"江圣","学号":"212206016"}, ...]} 对象数组;
 * V1 代码另兼容旧格式 {@code "张三(2122001)"} 字符串数组与逗号分隔纯姓名。
 * 三种都要认,否则 V1/V2 存量数据迁进 v3 后一个成员都关联不上。
 *
 * @author AwardIE
 */
class StudentMembersTest {

    @Test
    void parsesV1JsonObjectArray() {
        // V1 实际库里的格式
        String json = "[{\"姓名\":\"江圣\",\"学号\":\"212206016\"},{\"姓名\":\"陈加羽\",\"学号\":\"212306215\"}]";
        List<MemberRef> refs = StudentMembers.parseMembers(json);
        assertThat(refs).hasSize(2);
        assertThat(refs.get(0).name()).isEqualTo("江圣");
        assertThat(refs.get(0).studentId()).isEqualTo("212206016");
        assertThat(refs.get(1).studentId()).isEqualTo("212306215");
    }

    @Test
    void parsesLegacyNameWithIdStringArray() {
        List<MemberRef> refs = StudentMembers.parseMembers("[\"张三(212206016)\",\"李四(212206017)\"]");
        assertThat(refs).hasSize(2);
        assertThat(refs.get(0).name()).isEqualTo("张三");
        assertThat(refs.get(0).studentId()).isEqualTo("212206016");
    }

    @Test
    void parsesDelimitedText() {
        List<MemberRef> refs = StudentMembers.parseMembers("张三(212206016)、李四(212206017),王五");
        assertThat(refs).hasSize(3);
        assertThat(refs.get(0).studentId()).isEqualTo("212206016");
        assertThat(refs.get(1).studentId()).isEqualTo("212206017");
        // 纯姓名项:学号为空,由调用方跳过(不按姓名匹配,重名会错配)
        assertThat(refs.get(2).name()).isEqualTo("王五");
        assertThat(refs.get(2).studentId()).isNull();
    }

    @Test
    void handlesBlankAndNull() {
        assertThat(StudentMembers.parseMembers(null)).isEmpty();
        assertThat(StudentMembers.parseMembers("")).isEmpty();
        assertThat(StudentMembers.parseMembers("   ")).isEmpty();
        assertThat(StudentMembers.parseMembers(",,,、")).isEmpty();
    }

    @Test
    void fallsBackToDelimitedOnBrokenJson() {
        // 非法 JSON 不应让整行导入失败,退回分隔文本解析
        List<MemberRef> refs = StudentMembers.parseMembers("[{坏JSON, 张三(212206016)");
        assertThat(refs).isNotEmpty();
    }

    @Test
    void serializesToV1ObjectArrayFormat() {
        // 输出必须与 V1 库格式一致,这样 ETL 迁来的与新导入的同构
        String json = StudentMembers.toJson("张三(212206016)、李四");
        assertThat(json).contains("姓名").contains("学号").contains("212206016");
        assertThat(json).startsWith("[{").endsWith("}]");
    }

    @Test
    void serializesEmptyToEmptyArray() {
        assertThat(StudentMembers.toJson((String) null)).isEqualTo("[]");
        assertThat(StudentMembers.toJson("")).isEqualTo("[]");
        assertThat(StudentMembers.toJson((List<MemberRef>) null)).isEqualTo("[]");
    }

    @Test
    void isStudentIdRecognizesOnlyDigitIds() {
        // 决定"能不能拿去匹配用户"——姓名/短数字/含字母都不行
        assertThat(InnovationStudentMatcher.isStudentId("212206030")).isTrue();   // V1/V2 实际 9 位
        assertThat(InnovationStudentMatcher.isStudentId("21220603012")).isTrue(); // 更长也接受
        assertThat(InnovationStudentMatcher.isStudentId("1234567")).isFalse();     // 7 位:低于下限
        assertThat(InnovationStudentMatcher.isStudentId("2024")).isFalse();        // 短数字不是学号
        assertThat(InnovationStudentMatcher.isStudentId("张三")).isFalse();
        assertThat(InnovationStudentMatcher.isStudentId("21220603A")).isFalse();   // 含字母
        assertThat(InnovationStudentMatcher.isStudentId(null)).isFalse();
        assertThat(InnovationStudentMatcher.isStudentId("")).isFalse();
    }

}
