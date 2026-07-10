# tools\view_templates_app.py

用于管理奖状提取规则的。

# tools\prompt_optimizer_app.py

图片导入。

get_data.py 根据君石给出的报告，进行数据核对，确认丢失了哪些奖状。

# tools\clean_all.py

清理奖状数据工具（菜单选择：奖状、模板、缓存、待审核、files 等）。

# tools\clean_expired_pending.py

定时清理超时的 pending 记录（status='pending'，超过配置时间未提交）及对应 files/temp_upload 会话目录与文件。  
配置：config/settings.json 中 `pending_cleanup.expire_minutes`（默认 30）。  
用法：`python tools/clean_expired_pending.py`；`--dry-run` 仅统计不执行。  
定时任务：由系统 cron（Linux）或计划任务（Windows）定期执行，例如每 15 分钟一次。

# tools\clean_all_awards.py

清理所有的奖状和从奖状中生成的规则。在代码中对奖状抽取，规则重建等大修改后，执行，然后再重新导入。

# tools\get_data.py

从数据中导出并且核对数据库内容

# tools\data_export_app.py

导出数据

# tools/create_award_templates.py

扫描数据库的奖状创建奖状模板

# 测试模板

test/test_award_template_ocr.py

把测试的文件放入test/extract.py可以观察结果。