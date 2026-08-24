# 路径可移植性说明（部署相关）

项目部署到不同服务器或目录时，若在数据库或 URL 中存储/使用**绝对路径**，会导致文件访问失败。本文档说明当前约定与已做处理。

## 一、约定与原则

1. **禁止在业务数据中存储本机绝对路径**  
   数据库字段、API 返回、前端 URL 中应使用**相对路径**或由配置解析出的路径，以便换机器/换目录后仍能正确访问。

2. **统一根目录**  
   - **files_root**（配置项 `files`）：业务文件根目录，如奖状、专利、软著、实验室、**temp_upload**、**review** 等均在其下。  
   - **temp_dir**（配置项 `temp_dir`）：仅用于少数临时场景（如手动导入的原始上传目录）；主流导入流程已改为使用 `files_root/temp_upload/`。

3. **相对路径格式**  
   - 上传/审核流程：`temp_upload/{session_id}/{filename}` 或 `review/{session_id}/{filename}`，均相对于 **files_root**。  
   - 实验室封面：`images/laboratory_covers/{filename}`，相对于静态资源或 files 根由配置约定。

## 二、已做处理

### 1. Pending 成果 file_path

- **存储**：`pending_achievements.file_path` 与 `achievement_data['file_path']` 统一存**相对路径**（如 `temp_upload/session_id/hash.ext`），不再存绝对路径。
- **写入处**：  
  - 管理员/教师/学生「上传并识别」：使用 `upload_result.relative_path`。  
  - 管理员「手动导入」：先将文件复制到 `files_root/temp_upload/{session_id}/`，再存 `temp_upload/{session_id}/{filename}`。
- **读取/移动**：  
  - `UnifiedFileManager.resolve_path(path)`：相对路径按 files_root 解析，绝对路径原样返回（兼容历史数据）。  
  - `move_to_review`、`safe_delete_with_file`、`ReviewService` 中访问文件时均通过 `resolve_path` 或 `files_root / path` 得到实际路径。

### 2. 文件访问路由

- **admin**：`/admin/file-import/file/<path>`  
  - 支持 `temp_upload/...`（在 files_root 下）、绝对路径（且必须在 files_root/temp_upload 下）、其他相对路径（在 config temp_dir 下）。
- **teacher**：`/teacher/achievement-submit/file/<path>`  
  - 同上，支持 temp_upload、绝对路径、config temp_dir。
- **student**：`/student/achievement-submit/file/<path>`  
  - 同上。
- **teacher/student 审核文件**：`achievement_review_file` 使用 `files_root / file_path`，file_path 为相对路径（如 `review/...`）。

### 3. 实验室

- **cover_image**：存相对路径 `images/laboratory_covers/{filename}`，不存绝对路径。  
- 实验室图片/下载：路径均相对于 files_root 或配置约定目录，不依赖本机绝对路径。

### 4. 奖状/专利/软著/其他业务文件

- 奖状：库中存 `image_hash`，实际路径由 `images_dir`/files_root + hash 在运行时解析。  
- 专利/软著/其他文件：由统一文件管理器或各 Manager 按配置的 files_dir/files_root 解析，不依赖绝对路径。

## 三、部署检查清单

- [ ] 配置中 **files**（files_root）、**temp_dir**、**database** 等路径使用相对项目根的配置或环境变量，不要写死本机绝对路径。  
- [ ] 迁移数据时，若库中存在历史绝对路径，保留即可；`resolve_path` 会兼容，新数据均为相对路径。  
- [ ] 迁移时需同步 **files 目录**（含 temp_upload、review、awards 等）到新服务器，并保证配置的 files_root 指向该目录。  
- [ ] 测试/脚本中若有硬编码绝对路径（如 `D:\...`、`/var/...`），仅限本地或 CI 使用，不要进入生产数据或 API 返回。

## 四、仍可能涉及“路径”的模块（未改存储格式）

- **achievement_manager（活动—成果）**：若仍在使用，其 `evidence_file_path` 可能来自 `award.get_image_path()` 的字符串形式，在极端情况下可能带绝对路径；该模块已标注废弃，新功能不依赖。  
- **测试/脚本**：如 `tests/extract_test.py`、`tests/quick_extract_test.py` 等中的测试图片路径多为本地绝对路径，仅测试用，不影响部署。

## 五、小结

- 业务数据与 URL 中**不再写入本机绝对路径**，统一使用相对路径（相对于 files_root 或 temp_dir）。  
- 访问文件时通过 **UnifiedFileManager.resolve_path** 或 **files_root + 相对路径** 解析，部署到新服务器后只要配置好 files_root 并迁移 files 目录即可正常使用。
