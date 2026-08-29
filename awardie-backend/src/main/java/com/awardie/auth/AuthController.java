package com.awardie.auth;

import java.security.Principal;
import java.time.Instant;
import java.util.Map;

import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.authentication.dao.DaoAuthenticationProvider;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.security.web.context.SecurityContextRepository;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import com.awardie.common.ApiResponse;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;

/** 登录/登出/改密(纵切面第一环;BR-4 首登强制改密,BR-6 密码强度)。 */
@RestController
@RequestMapping("/api/v2/auth")
public class AuthController {

    public record LoginRequest(@NotBlank String account, @NotBlank String password) {}

    public record ChangePasswordRequest(@NotBlank String oldPassword,
                                        @NotBlank @Pattern(regexp = "^(?=.*[A-Za-z])(?=.*\\d).{8,}$",
                                                message = "密码至少 8 位且同时包含字母与数字(BR-6)") String newPassword) {}

    private final UserRepository users;
    private final PasswordEncoder encoder;
    private final DaoAuthenticationProvider authProvider;
    private final SecurityContextRepository contextRepository = new HttpSessionSecurityContextRepository();

    public AuthController(UserRepository users, PasswordEncoder encoder, DaoAuthenticationProvider authProvider) {
        this.users = users;
        this.encoder = encoder;
        this.authProvider = authProvider;
    }

    @PostMapping("/login")
    public ApiResponse<Map<String, Object>> login(@RequestBody LoginRequest req, HttpServletRequest request) {
        // 走 DaoAuthenticationProvider:透明重哈希(UserDetailsPasswordService)由此触发,勿手工 matches 绕过
        Authentication auth;
        try {
            auth = authProvider.authenticate(
                    UsernamePasswordAuthenticationToken.unauthenticated(req.account(), req.password()));
        } catch (org.springframework.security.core.AuthenticationException e) {
            return ApiResponse.error(4010, "账号或密码错误");
        }
        UserEntity u = users.findByLoginCode(req.account()).orElse(null);
        if (u == null) {
            return ApiResponse.error(4010, "账号或密码错误");
        }
        if (u.getUserActivated() != null && !u.getUserActivated()) {
            return ApiResponse.error(4011, "账号未激活");
        }
        SecurityContextHolder.getContext().setAuthentication(auth);
        contextRepository.saveContext(SecurityContextHolder.getContext(), request, null);
        return ApiResponse.ok(Map.of(
                "id", u.getId(),
                "name", u.getName() == null ? "" : u.getName(),
                "role", u.getRole(),
                "needsPasswordChange", Boolean.TRUE.equals(u.getNeedsPasswordChange())));
    }

    @PostMapping("/logout")
    public ApiResponse<Void> logout(HttpServletRequest request) {
        var session = request.getSession(false);
        if (session != null) {
            session.invalidate();
        }
        SecurityContextHolder.clearContext();
        return ApiResponse.ok(null, "已登出");
    }

    @GetMapping("/me")
    public ApiResponse<Map<String, Object>> me(Principal principal) {
        if (principal == null) {
            return ApiResponse.error(4010, "未登录");
        }
        UserEntity u = users.findByLoginCode(principal.getName()).orElse(null);
        if (u == null) {
            return ApiResponse.error(4010, "未登录");
        }
        return ApiResponse.ok(Map.of(
                "id", u.getId(),
                "loginCode", u.getLoginCode(),
                "name", u.getName() == null ? "" : u.getName(),
                "role", u.getRole(),
                "needsPasswordChange", Boolean.TRUE.equals(u.getNeedsPasswordChange())));
    }

    @PostMapping("/password")
    public ApiResponse<Void> changePassword(@org.springframework.validation.annotation.Validated @RequestBody ChangePasswordRequest req, Principal principal) {
        UserEntity u = users.findByLoginCode(principal.getName()).orElse(null);
        if (u == null) {
            return ApiResponse.error(4010, "未登录");
        }
        if (u.getPasswordHash() == null || !encoder.matches(req.oldPassword(), u.getPasswordHash())) {
            return ApiResponse.error(4012, "原密码错误");
        }
        u.setPasswordHash(encoder.encode(req.newPassword()));
        u.setNeedsPasswordChange(false); // BR-4 完成
        u.setUpdatedAt(Instant.now());
        users.save(u);
        return ApiResponse.ok(null, "密码已更新");
    }
}
