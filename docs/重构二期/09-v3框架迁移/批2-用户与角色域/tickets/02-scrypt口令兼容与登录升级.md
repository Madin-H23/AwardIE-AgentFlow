# 02 — scrypt 口令兼容+登录升级(含集成测试)

**What to build:** v2 的 1834 个 scrypt 口令用户在 v3 直接用原口令登录,且首次登录后自动升级为 BCrypt。业务模块新增 @Primary PasswordEncoder(scrypt 前缀→BouncyCastle 复算,其余→BCrypt,移植自 v2 WerkzeugCompatPasswordEncoder)+ AuthenticationSuccessEvent 监听器(登录成功后 scrypt→BCrypt 重编码落库);bcprov-jdk18on 依赖入 business pom。

**Blocked by:** None — can start immediately

**Status:** ready-for-agent

- [ ] 播种 scrypt 哈希用户(现场用同参数生成)→ MockMvc 登录 code 0 → DB 该行口令前缀变 $2 → 二次登录 code 0
- [ ] 若事件拿不到原始口令(credentials 已清):回退"仅兼容不升级"+文档挂账(不许静默 half-way)
- [ ] 批1 三例+全量套件不回归;p3c 0 违例
