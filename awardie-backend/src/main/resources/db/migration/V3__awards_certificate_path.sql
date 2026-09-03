-- 批 2 awards 证书链(D3a 拍板):awards 补证书文件引用,修复"物化后图链断裂"。
-- 存量回填:pending_achievements(archived)持有 files/v2 文件引用,按文件哈希接回 awards。
ALTER TABLE awards ADD COLUMN certificate_path VARCHAR(500);

UPDATE awards a
SET certificate_path = p.file_path
FROM pending_achievements p
WHERE a.image_hash = p.file_hash
  AND p.file_path IS NOT NULL
  AND a.certificate_path IS NULL;
