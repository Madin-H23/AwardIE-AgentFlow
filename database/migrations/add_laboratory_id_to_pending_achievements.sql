-- 添加 laboratory_id 字段到 pending_achievements 表
-- 迁移日期: 2026-01-28
-- 描述: 支持在导入时为 pending 记录预关联实验室

-- 检查字段是否存在，如果不存在则添加
-- SQLite 不支持 IF NOT EXISTS 语法用于 ALTER TABLE，所以需要在应用层处理
-- 或者直接执行，忽略错误（如果字段已存在）

ALTER TABLE pending_achievements ADD COLUMN laboratory_id INTEGER;
