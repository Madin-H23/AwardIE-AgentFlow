package com.awardie.auth.security;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.web.SecurityFilterChain;

import com.awardie.common.TraceIdFilter;

@Configuration
@EnableWebSecurity
public class SecurityConfig {

    private final AppUserDetailsService userDetailsService;
    private final WerkzeugCompatPasswordEncoder passwordEncoder;

    public SecurityConfig(AppUserDetailsService userDetailsService, WerkzeugCompatPasswordEncoder passwordEncoder) {
        this.userDetailsService = userDetailsService;
        this.passwordEncoder = passwordEncoder;
    }

    @Bean
    public DaoAuthenticationProvider daoAuthenticationProvider() {
        DaoAuthenticationProvider provider = new DaoAuthenticationProvider();
        provider.setUserDetailsService(userDetailsService);
        // 手工 new 的 provider 不会自动识别 UserDetailsPasswordService(仅 Boot 全局装配器做)——透明重哈希必须显式挂
        provider.setUserDetailsPasswordService(userDetailsService);
        provider.setPasswordEncoder(passwordEncoder);
        return provider;
    }

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
                // #16:Cookie 方案 CSRF(前端读 XSRF-TOKEN cookie 回传 X-XSRF-TOKEN 头)
                .csrf(csrf -> {
                    // 禁用 deferred token(6.1 默认):保证 GET 即落 XSRF cookie
                    var handler = new org.springframework.security.web.csrf.CsrfTokenRequestAttributeHandler();
                    handler.setCsrfRequestAttributeName(null);
                    csrf.csrfTokenRepository(
                            org.springframework.security.web.csrf.CookieCsrfTokenRepository.withHttpOnlyFalse())
                            .csrfTokenRequestHandler(handler);
                })
                .authorizeHttpRequests(auth -> auth
                        .requestMatchers("/api/v2/auth/login", "/api/v2/auth/csrf", "/actuator/health")
                        .permitAll()
                        .requestMatchers("/api/v2/**").authenticated()
                        .anyRequest().permitAll()) // 非 /api/v2 路径归 v1/Nginx 分流管
                .exceptionHandling(e -> e.authenticationEntryPoint((req, res, ex) -> {
                    res.setStatus(401);
                    res.setContentType("application/json;charset=UTF-8");
                    res.getWriter().write("{\"code\":4010,\"message\":\"未登录\",\"data\":null,\"traceId\":\"\",\"timestamp\":\"\"}");
                }))
                .formLogin(form -> form.disable())
                .httpBasic(basic -> basic.disable())
                .logout(logout -> logout.disable()); // 登出走 AuthController(统一 ApiResponse)
        return http.build();
    }
}
