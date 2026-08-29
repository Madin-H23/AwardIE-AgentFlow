package com.awardie.auth.security;

import java.util.List;

import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsPasswordService;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.awardie.auth.UserEntity;
import com.awardie.auth.UserRepository;

/** users.login_code 装载;实现 UserDetailsPasswordService → 登录成功自动透明重哈希(v1 scrypt → BCrypt)。 */
@Service
public class AppUserDetailsService implements UserDetailsService, UserDetailsPasswordService {

    private final UserRepository users;
    private final WerkzeugCompatPasswordEncoder encoder;

    public AppUserDetailsService(UserRepository users, WerkzeugCompatPasswordEncoder encoder) {
        this.users = users;
        this.encoder = encoder;
    }

    @Override
    public UserDetails loadUserByUsername(String loginCode) throws UsernameNotFoundException {
        UserEntity u = users.findByLoginCode(loginCode)
                .orElseThrow(() -> new UsernameNotFoundException("账号不存在"));
        boolean disabled = u.getUserActivated() != null && !u.getUserActivated();
        return User.withUsername(u.getLoginCode())
                .password(u.getPasswordHash() == null ? "" : u.getPasswordHash())
                .authorities(List.of(new SimpleGrantedAuthority("ROLE_" + u.getRole().toUpperCase())))
                .accountLocked(false)
                .disabled(disabled)
                .build();
    }

    @Override
    @Transactional
    public UserDetails updatePassword(UserDetails user, String newPassword) {
        UserEntity u = users.findByLoginCode(user.getUsername())
                .orElseThrow(() -> new UsernameNotFoundException("账号不存在"));
        u.setPasswordHash(encoder.encode(newPassword));
        u.setUpdatedAt(java.time.Instant.now());
        users.save(u);
        return new User(user.getUsername(), u.getPasswordHash(), user.getAuthorities());
    }
}
