-- 批 2 数据修正:V3 回填带入的 v1 时代路径(temp_upload/* 等)不在 files/v2 白名单内且文件多已失存,
-- 置空使其回退到"仅有哈希,可上传补齐"状态;批 3 ETL 按哈希重连真实存量文件。
UPDATE awards
SET certificate_path = NULL
WHERE certificate_path IS NOT NULL
  AND position('files/v2/' in certificate_path) <> 1
  AND position('files\v2\' in certificate_path) <> 1;
