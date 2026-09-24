package cn.iocoder.yudao.module.business.service.pendingsubmission;

import cn.iocoder.yudao.module.system.dal.dataobject.permission.RoleDO;
import cn.iocoder.yudao.module.system.dal.dataobject.permission.UserRoleDO;
import cn.iocoder.yudao.module.system.dal.mysql.permission.RoleMapper;
import cn.iocoder.yudao.module.system.dal.mysql.permission.UserRoleMapper;
import jakarta.annotation.Resource;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Set;

/**
 * 提交人类型解析(批4):从当前用户的芋道角色 code 推导 v2 的 submitter_type
 *
 * <p>不信任前端入参——submitter_type 一律由服务端按登录用户的实际角色推导。
 * 角色 code 与 v2 role 的映射:awardie_student→student、awardie_teacher→teacher、
 * awardie_admin→admin;未匹配到业务角色时按 student 兜底(学生门户是主入口)。
 *
 * @author AwardIE
 */
@Component
public class SubmitterTypeResolver {

    /** 提交人类型取值(与 v2 submitter_type 同名) */
    public static final String TYPE_STUDENT = "student";
    public static final String TYPE_TEACHER = "teacher";
    public static final String TYPE_ADMIN = "admin";
    /** 芋道角色 code(v2 role 的映射源,批2 建) */
    private static final String CODE_ADMIN = "awardie_admin";
    private static final String CODE_TEACHER = "awardie_teacher";

    @Resource
    private UserRoleMapper userRoleMapper;
    @Resource
    private RoleMapper roleMapper;

    /**
     * 解析提交人类型
     *
     * @param userId 登录用户编号
     * @return student/teacher/admin
     */
    public String resolve(Long userId) {
        List<UserRoleDO> userRoles = userRoleMapper.selectListByUserId(userId);
        if (userRoles.isEmpty()) {
            return TYPE_STUDENT;
        }
        List<RoleDO> roles = roleMapper.selectByIds(
                userRoles.stream().map(UserRoleDO::getRoleId).toList());
        Set<String> codes = roles.stream().map(RoleDO::getCode).collect(java.util.stream.Collectors.toSet());
        if (codes.contains(CODE_ADMIN)) {
            return TYPE_ADMIN;
        }
        if (codes.contains(CODE_TEACHER)) {
            return TYPE_TEACHER;
        }
        return TYPE_STUDENT;
    }

}
