package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.framework.tenant.core.context.TenantContextHolder;
import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.mysql.user.AdminUserMapper;
import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Component;

import static cn.iocoder.yudao.framework.security.core.util.SecurityFrameworkUtils.getLoginUser;

/**
 * 审核操作人信息(批5):按登录用户 id 取"账号 + 姓名",供审核留痕落库
 *
 * <p>为何不取 {@code getAuthentication().getName()}:芋道是 token 认证,该方法返回的是
 * **token 字符串本身**(数十位),不是账号——写进 operator_code 会直接超列长(实测报
 * Data truncation)。故按 id 查用户表拿 username + nickname。
 *
 * @author AwardIE
 */
@Component
public class ReviewOperatorResolver {

    @Resource
    private AdminUserMapper adminUserMapper;

    /**
     * 当前操作人信息
     *
     * @return 账号与姓名
     */
    public Operator current() {
        if (getLoginUser() == null) {
            return new Operator("", "");
        }
        return of(getLoginUser().getId());
    }

    /**
     * 指定用户的操作人信息
     *
     * @param userId 用户编号
     * @return 账号与姓名(查不到时返回空串,不阻断审核)
     */
    public Operator of(Long userId) {
        if (userId == null) {
            return new Operator("", "");
        }
        AdminUserDO user = adminUserMapper.selectOne(new LambdaQueryWrapper<AdminUserDO>()
                .eq(AdminUserDO::getId, userId)
                .eq(AdminUserDO::getTenantId, TenantContextHolder.getRequiredTenantId()));
        if (user == null) {
            return new Operator("", "");
        }
        return new Operator(user.getUsername(), user.getNickname() == null ? "" : user.getNickname());
    }

    /**
     * 操作人
     *
     * @param code 账号
     * @param name 姓名
     */
    public record Operator(String code, String name) {
    }

}
