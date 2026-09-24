# 04 — 存量用户 ETL 脚本+实跑验证

**What to build:** `scripts/etl_v2_users_to_v3.py`(venv python,psycopg2+pymysql):PG awardie_dev.users 1834 条 → MySQL awardie_v3 的 system_users+awardie_user_profile;显式带 v2 id;字段映射按 spec(login_code→username、name→nickname、phone→mobile、user_activated→status、role→三角色);username ON DUPLICATE 幂等;末尾抬 AUTO_INCREMENT;login_code 唯一性内置校验(有重复报错中止);对 awardie_v3 dev 库实跑并记录验证(计数/id 保真/hash 前缀/二跑幂等)。

**Blocked by:** 03(角色与扩展表须先在 dev 库存在)

**Status:** ready-for-agent

- [ ] 实跑:system_users=1834(含 id=1 覆盖 stock admin)、profile=1834;抽查 id 一一对应;hash 前缀仍为 scrypt
- [ ] 二跑计数不变(幂等);AUTO_INCREMENT > max(id)
- [ ] 取一个 v2 学生账号口令在 v3 登录成功(升级路径已在 02 覆盖,此处验 ETL 保真)
- [ ] 验证记录入 03-测试.md
