package cn.iocoder.yudao.module.business.service.template;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateCreateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplateUpdateReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesPageReqVO;
import cn.iocoder.yudao.module.business.controller.admin.template.vo.TemplatesRespVO;
import cn.iocoder.yudao.module.business.dal.dataobject.template.TemplatesDO;

import java.io.IOException;

/**
 * AwardIE 证书模板 Service(批7)
 *
 * @author AwardIE
 */
public interface TemplateService {

    /**
     * 创建模板
     *
     * @param createReqVO  创建参数
     * @param filename    样本图原始文件名
     * @param fileBytes   样本图内容
     * @return 新建模板编号
     * @throws IOException 样本图落盘失败
     */
    Long createTemplate(TemplateCreateReqVO createReqVO, String filename, byte[] fileBytes) throws IOException;

    /**
     * 更新模板(仅规则字段;竞赛与授予角色不可改)
     *
     * @param id         模板编号
     * @param updateReqVO 更新参数
     */
    void updateTemplate(Long id, TemplateUpdateReqVO updateReqVO);

    /**
     * 删除模板(逻辑删除 + 回收样本图物理文件)
     *
     * @param id 模板编号
     */
    void deleteTemplate(Long id);

    /**
     * 获取模板详情
     *
     * @param id 模板编号
     * @return 模板详情(含竞赛名与"是否有样本图")
     */
    TemplatesRespVO getTemplate(Long id);

    /**
     * 读回模板样本图字节
     *
     * @param id 模板编号
     * @return 样本图内容
     * @throws IOException 读盘失败
     */
    byte[] getSampleImage(Long id) throws IOException;

    /**
     * 样本图 Content-Type
     *
     * @param id 模板编号
     * @return Content-Type
     */
    String getSampleImageContentType(Long id);

    /**
     * 模板分页列表
     *
     * @param pageReqVO 分页参数
     * @return 模板分页结果
     */
    PageResult<TemplatesRespVO> getTemplatePage(TemplatesPageReqVO pageReqVO);

    /**
     * 取模板(供 AI 端点内部使用)
     *
     * @param id 模板编号
     * @return 模板
     */
    TemplatesDO getTemplateDO(Long id);

    /**
     * 序列化模板规则为 Worker 的 template_rule_json 入参
     *
     * @param template 模板
     * @return 规则 JSON
     */
    String buildRuleJson(TemplatesDO template);

}
