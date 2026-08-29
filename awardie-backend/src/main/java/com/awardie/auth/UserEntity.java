package com.awardie.auth;

import java.time.Instant;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/** users 表映射(仅登录相关列;表由 V1__baseline 建立且含更多列,未映射列不参与)。 */
@Entity
@Table(name = "users")
public class UserEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "id")
    private Integer id;

    @Column(name = "login_code", nullable = false)
    private String loginCode;

    @Column(name = "name")
    private String name;

    @Column(name = "role", nullable = false)
    private String role;

    @Column(name = "password_hash")
    private String passwordHash;

    @Column(name = "user_activated")
    private Boolean userActivated;

    @Column(name = "needs_password_change")
    private Boolean needsPasswordChange;

    @Column(name = "updated_at")
    private Instant updatedAt;

    public Integer getId() { return id; }
    public String getLoginCode() { return loginCode; }
    public String getName() { return name; }
    public String getRole() { return role; }
    public String getPasswordHash() { return passwordHash; }
    public void setPasswordHash(String passwordHash) { this.passwordHash = passwordHash; }
    public Boolean getUserActivated() { return userActivated; }
    public Boolean getNeedsPasswordChange() { return needsPasswordChange; }
    public void setNeedsPasswordChange(Boolean needsPasswordChange) { this.needsPasswordChange = needsPasswordChange; }
    public Instant getUpdatedAt() { return updatedAt; }
    public void setUpdatedAt(Instant updatedAt) { this.updatedAt = updatedAt; }
}
