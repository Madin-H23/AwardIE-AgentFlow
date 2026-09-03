-- 批 1 文件域收敛(D1a/D2a 拍板):templates 样本图 BYTEA→目录存储过渡列。
-- 数据由 scripts/migrate_template_image_blobs.py 一次性搬迁并置空 blob;列本体于批 3 迁移中 DROP。
ALTER TABLE templates ADD COLUMN sample_image_path VARCHAR(500);
