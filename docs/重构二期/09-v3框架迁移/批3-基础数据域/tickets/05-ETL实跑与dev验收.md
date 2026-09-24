# 05 — v2 两域 ETL 脚本 + dev 库实跑 + swagger/curl 验收

**What to build:** `scripts/etl_v2_competitions_laboratories_to_v3.py`(仿批2 ETL:环境变量取口令、显式保 v2 id、ON DUPLICATE KEY UPDATE 幂等、末尾抬 AUTO_INCREMENT、输出计数/id 差校验);前置物理清理 dev 库批1 测试遗留(awardie_laboratories 11 行 deleted=1);竞赛全字段(布尔→BIT)、实验室 name/description(cover_image 不迁,批4);对 dev 库实跑两遍并记录;swagger 截图(两域端点)+ curl 全链路实证(登录→建竞赛→重名拒→建实验室→分页→引用拒绝→删除);测试文件清理(临时引用表/脚本产物)确认;02-实施.md 落盘三道闸结论。

**Blocked by:** 03(竞赛 CRUD)、04(实验室补全)——ETL 需表与服务就位;验收需端点可调

**Status:** ready-for-agent

- [ ] ETL 两跑:dev competitions=218、laboratories=5;id 与 v2 集合差为空;AUTO_INCREMENT>max(id)
- [ ] 布尔字段迁移正确(white/watch/auto_added 对齐 v2 计数 117/51/45)
- [ ] swagger 截图两域端点可见;curl 链路含引用拒绝实证
- [ ] 测试临时表/产物清理;02-实施.md 含与 v2 的语义差声明
