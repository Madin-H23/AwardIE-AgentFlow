package cn.iocoder.yudao.module.business.framework.security;

import org.springframework.beans.BeansException;
import org.springframework.beans.factory.support.BeanDefinitionRegistry;
import org.springframework.beans.factory.support.BeanDefinitionRegistryPostProcessor;
import org.springframework.stereotype.Component;

/**
 * 口令编码器 Bean 接管(批2):摘除上游 YudaoSecurityAutoConfiguration 的 "passwordEncoder" bean 定义,
 * 让同名的 {@link AwardiePasswordEncoder}(scrypt 兼容)接管。
 *
 * 为什么需要:芋道 {@code AdminUserServiceImpl} 等用 {@code @Resource} 按名称注入 PasswordEncoder,
 * 解析到 bean 名 "passwordEncoder"——上游自动配置的 BCrypt 编码器占用该名,@Primary 对按名注入无效,
 * scrypt 存量口令将永远校验失败。上游自动配置是普通 @Bean(无 @ConditionalOnMissingBean),无法通过
 * 定义顺序覆盖,故在实例化前摘除其定义(本 fork 对上游的最小侵入,上游文件零改动)。
 *
 * @author AwardIE
 */
@Component
public class PasswordEncoderBeanOverride implements BeanDefinitionRegistryPostProcessor {

    /** 上游自动配置的编码器 bean 名(芋道 @Resource 按名注入的目标) */
    private static final String UPSTREAM_ENCODER_BEAN = "passwordEncoder";

    @Override
    public void postProcessBeanDefinitionRegistry(BeanDefinitionRegistry registry) throws BeansException {
        if (registry.containsBeanDefinition(UPSTREAM_ENCODER_BEAN)) {
            registry.removeBeanDefinition(UPSTREAM_ENCODER_BEAN);
        }
    }
}
