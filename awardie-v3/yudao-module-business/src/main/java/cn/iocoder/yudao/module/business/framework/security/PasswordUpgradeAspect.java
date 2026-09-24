package cn.iocoder.yudao.module.business.framework.security;

import cn.iocoder.yudao.module.system.dal.dataobject.user.AdminUserDO;
import cn.iocoder.yudao.module.system.dal.mysql.user.AdminUserMapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import jakarta.annotation.Resource;
import org.aspectj.lang.ProceedingJoinPoint;
import org.aspectj.lang.annotation.Around;
import org.aspectj.lang.annotation.Aspect;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

/**
 * 口令升级切面(批2):口令校验通过且存量哈希为 scrypt 时,以 BCrypt 重编码落库。
 *
 * 为什么用 AOP 而非事件监听器:芋道登录是服务级手工校验(AdminAuthServiceImpl.authenticate →
 * userService.isPasswordMatch),不经 Spring Security AuthenticationManager,不发布
 * AuthenticationSuccessEvent。isPasswordMatch 由 AuthService 跨 bean 调用(非自调用),可被代理;
 * 且所有调用点(登录/修改密码)都持有合法原始口令,升级安全。
 *
 * 定位方式:按旧哈希等值匹配(盐值随机,不会误匹配其他用户),免去传入用户 id。
 *
 * @author AwardIE
 */
@Aspect
@Component
public class PasswordUpgradeAspect {

    /** v2 存量 werkzeug scrypt 哈希前缀 */
    private static final String SCRYPT_PREFIX = "scrypt:";

    @Resource
    private AdminUserMapper userMapper;
    @Resource
    private PasswordEncoder passwordEncoder;

    @Around("execution(public boolean cn.iocoder.yudao.module.system.service.user.AdminUserServiceImpl.isPasswordMatch(String, String))")
    public Object aroundIsPasswordMatch(ProceedingJoinPoint pjp) throws Throwable {
        boolean matched = (boolean) pjp.proceed();
        if (matched) {
            String rawPassword = (String) pjp.getArgs()[0];
            String encodedPassword = (String) pjp.getArgs()[1];
            if (encodedPassword != null && encodedPassword.startsWith(SCRYPT_PREFIX)) {
                String upgraded = passwordEncoder.encode(rawPassword);
                userMapper.update(null, new LambdaUpdateWrapper<AdminUserDO>()
                        .eq(AdminUserDO::getPassword, encodedPassword)
                        .set(AdminUserDO::getPassword, upgraded));
            }
        }
        return matched;
    }
}
