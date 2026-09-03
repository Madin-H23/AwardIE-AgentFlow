-- 批 3 收口(D2a 拍板):模板样本图已全量迁 files/v2(V2 加列+脚本搬运置空),BYTEA 列退役。
-- 前置:scripts/migrate_template_image_blobs.py 已在目标库执行(awardie_dev 20/20;测试库/CI 无 blob 数据)。
ALTER TABLE templates DROP COLUMN sample_image_blob;
