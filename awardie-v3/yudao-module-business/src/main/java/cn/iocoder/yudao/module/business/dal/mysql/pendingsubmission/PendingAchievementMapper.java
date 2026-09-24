package cn.iocoder.yudao.module.business.dal.mysql.pendingsubmission;

import java.util.*;

import cn.iocoder.yudao.framework.common.pojo.PageResult;
import cn.iocoder.yudao.framework.mybatis.core.query.LambdaQueryWrapperX;
import cn.iocoder.yudao.framework.mybatis.core.mapper.BaseMapperX;
import cn.iocoder.yudao.module.business.dal.dataobject.pendingsubmission.PendingAchievementDO;
import org.apache.ibatis.annotations.Mapper;
import cn.iocoder.yudao.module.business.controller.admin.pendingsubmission.vo.*;

/**
 * AwardIE 待审成果 Mapper
 *
 * @author AwardIE
 */
@Mapper
public interface PendingAchievementMapper extends BaseMapperX<PendingAchievementDO> {

    /**
     * 分页查询待审成果(类型/提交人类型/状态/创建时间区间,ID 倒序)
     *
     * @param reqVO 分页参数
     * @return 待审成果分页结果
     */
    default PageResult<PendingAchievementDO> selectPage(PendingAchievementPageReqVO reqVO) {
        return selectPage(reqVO, new LambdaQueryWrapperX<PendingAchievementDO>()
                .eqIfPresent(PendingAchievementDO::getAchievementType, reqVO.getAchievementType())
                .eqIfPresent(PendingAchievementDO::getSubmitterType, reqVO.getSubmitterType())
                .eqIfPresent(PendingAchievementDO::getStatus, reqVO.getStatus())
                // 我的提交:按提交人过滤(数据隔离的第二道保险,权限点之外)
                .eqIfPresent(PendingAchievementDO::getSubmitterId, reqVO.getSubmitterId())
                .betweenIfPresent(PendingAchievementDO::getCreateTime, reqVO.getCreateTime())
                .orderByDesc(PendingAchievementDO::getId));
    }

    /**
     * 按文件哈希 + 状态查(提交去重用;只查 pending,与 v2 语义一致)
     *
     * @param fileHash 文件 SHA-256
     * @param status   状态
     * @return 命中的待审成果,无则 null
     */
    default PendingAchievementDO selectByFileHashAndStatus(String fileHash, String status) {
        return selectOne(new LambdaQueryWrapperX<PendingAchievementDO>()
                .eq(PendingAchievementDO::getFileHash, fileHash)
                .eq(PendingAchievementDO::getStatus, status));
    }

}