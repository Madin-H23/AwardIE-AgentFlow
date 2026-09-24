package cn.iocoder.yudao.module.business.dal.dataobject.template;

import cn.iocoder.yudao.framework.mybatis.core.dataobject.BaseDO;
import com.baomidou.mybatisplus.annotation.KeySequence;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;
import lombok.ToString;

/**
 * AwardIE 证书模板 DO(批7)
 *
 * <p>JSON 列在 DO 里按 String 承载(MyBatis 自动转换),出入参的结构化转换在 service 层做。
 *
 * <p>granted_role 提为独立列(v2 藏在 default_fields JSONB 里):唯一性"同竞赛+同角色"
 * 因此可走列比较,且编辑时改不掉它——v2 改 default_fields 即可绕过唯一性,是缺陷不是语义。
 *
 * @author AwardIE
 * <p>
 * KeySequence 用于 Oracle、PostgreSQL、Kingbase、DB2、H2 数据库的主键自增;MySQL 等数据库可不写。
 */
@TableName("awardie_templates")
@KeySequence("awardie_templates_seq")
@Data
@EqualsAndHashCode(callSuper = true)
@ToString(callSuper = true)
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TemplatesDO extends BaseDO {

    /**
     * 主键
     */
    @TableId
    private Long id;
    /**
     * 模板类型(仅 AWARD 奖状)
     */
    private String templateType;
    /**
     * 竞赛编号
     */
    private Long competitionId;
    /**
     * 授予角色(学生/教师)
     */
    private String grantedRole;
    /**
     * 抽取文本最小长度(0=不限)
     */
    private Integer minLength;
    /**
     * 抽取文本最大长度(0=不限)
     */
    private Integer maxLength;
    /**
     * 关键词(JSON 数组字符串)
     */
    private String keywords;
    /**
     * 样本文本
     */
    private String sampleText;
    /**
     * 样本抽取结果(JSON 对象字符串)
     */
    private String sampleExtracted;
    /**
     * 默认字段(JSON 对象字符串)
     */
    private String defaultFields;
    /**
     * 交给 LLM 的字段(JSON 对象字符串)
     */
    private String llmFields;
    /**
     * 输出语言
     */
    private String language;
    /**
     * 是否需要翻译
     */
    private Boolean needTranslate;
    /**
     * 样本图相对路径(批4 文件域)
     */
    private String sampleImagePath;

}
