# Admin 路由说明文档

本文档描述管理员端（`/admin`）下所有蓝图与路由的职责，以及重要路由的实现要点。所有路由均需管理员角色（`require_role('admin')` 或 `require_role_api('admin')`）。

**URL 前缀**：所有下述路径均以 `/admin` 为前缀，例如 `/admin/dashboard`、`/admin/competitions`。

---

## 一、蓝图与文件对应关系

| 蓝图名 | 文件 | 职责概要 |
|--------|------|----------|
| `admin` | `app/routes/admin.py` | 仪表盘、竞赛/学生/教师管理、系统设置、自动归档 |
| `admin_achievement` | `app/routes/admin_achievement.py` | 成果汇总页、文件导入（辅助函数在 `app/routes/file_import_helpers.py`） |
| `admin_awards` | `app/routes/admin_awards.py` | 奖状列表/编辑/删除/图片/刷新、成果页奖状 Tab API |
| `admin_export` | `app/routes/admin_export.py` | 数据导出（系年度总结、学工/教师个人导出） |
| `admin_laboratory` | `app/routes/admin_laboratory.py` | 实验室 CRUD、成果/竞赛关联、图片与下载资源 |
| `admin_templates` | `app/routes/admin_templates.py` | 奖状模板管理、刷新、测试、校验规则 API |
| `admin_patents` | `app/routes/admin_patents.py` | 专利列表/详情/创建/编辑/删除、查重 API |
| `admin_software` | `app/routes/admin_software.py` | 软著列表/详情/创建/编辑/删除、查重与批量删除 |
| `admin_innovation` | `app/routes/admin_innovation.py` | 大创列表/详情/创建/编辑/删除、查重 API |
| `admin_review` | `app/routes/admin_review.py` | 成果审核（待审列表、单条审核、批量通过、校验） |
| `admin_other_files` | `app/routes/admin_other_files.py` | 其他类型文件列表/详情/上传/下载/编辑/删除、预览 API |

---

## 二、admin（admin.py）— 仪表盘与基础数据

### 路由列表

| 路径 | 方法 | 作用 |
|------|------|------|
| `/` | GET | 管理员首页，同 dashboard |
| `/dashboard` | GET | 仪表盘页，渲染 `admin/dashboard.html` |
| `/api/config/competition-levels` | GET | 获取竞赛等级配置（列表 + 颜色映射），来自 `config/settings.json` |
| `/api/competitions/add` | POST | 快速添加竞赛（仅名称，别名等为空） |
| `/api/competitions/<id>/add-alias` | POST | 为竞赛添加别名 |
| `/competitions` | GET | 竞赛列表页 |
| `/competitions/<id>` | GET | 竞赛详情 |
| `/competitions/new` | GET, POST | 新建竞赛表单与提交 |
| `/competitions/<id>/edit` | GET, POST | 编辑竞赛 |
| `/competitions/<id>` | DELETE | 删除竞赛 |
| `/students` | GET | 学生列表（分页、按姓名/学号/ID 搜索） |
| `/students/new` | GET, POST | 新建学生 |
| `/students/<id>/edit` | GET, POST | 编辑学生 |
| `/students/<id>` | DELETE | 删除学生 |
| `/teachers` | GET | 教师列表（分页、搜索） |
| `/teachers/new` | GET, POST | 新建教师 |
| `/teachers/<id>/edit` | GET, POST | 编辑教师 |
| `/teachers/<id>` | DELETE | 删除教师 |
| `/api/students/search` | GET | 学生搜索（供前端联想等） |
| `/api/teachers/search` | GET | 教师搜索 |
| `/api/laboratories` | GET | 实验室列表（供下拉等） |
| `/api/students/duplicates` | GET | 学号重复检测 |
| `/settings` | GET | 系统设置页（**实际生效**，见下） |
| `/settings/ocr-status` | GET | 获取 OCR 供应商状态（当前使用的高精度、各供应商禁用状态及故障理由） |
| `/settings/ocr-provider/reenable` | POST | 重新启用某 OCR 供应商（清除禁用状态） |
| `/settings/ocr-provider/set-current` | POST | 将某 OCR 供应商设为当前默认（写 settings.json 并清除该供应商禁用状态） |
| `/settings/save` | POST | 保存系统设置（**实际生效**） |
| `/settings/auto-archive/update` | POST | 更新自动归档配置 |

### 重要实现要点

- **竞赛等级与颜色**：`api_get_competition_levels` 从 `get_config()` 读取 `validation.competition_levels` 与 `ui.competition_level_colors`，缺失时抛 `ValueError`，禁止硬编码默认值。
- **竞赛快速添加**：`api_add_competition` 用 `competition_manager.match_competition(name)` 判重，再 `add_competition(name=..., alias_list="", is_auto_added=False)`。
- **学生/教师列表**：无搜索时直接 SQL 分页（`students`/`teachers` 表）；有搜索时用 manager 按姓名/工号/学号/ID 查找后内存分页。
- **设置与自动归档**：`/settings` 与 `/settings/save` 由 **admin.py** 提供。
- **OCR 供应商状态**：高精度 OCR 调用失败（如 429）时，引擎会将该供应商标记为不可用并自动尝试下一可用高精度；全部不可用时回退到低精度（rapid）。管理员在系统设置页可查看**当前使用的高精度供应商**、各供应商的**正常/已禁用**状态及**故障理由/禁用时间**，并可**重新启用**某供应商或**设为当前**默认。状态持久化在 `config/ocr_runtime.json`（路径由 `config/settings.json` 的 `ocr.runtime_status_path` 指定）。

---

## 三、admin_achievement（admin_achievement.py）— 成果汇总与文件导入

### 路由列表（按功能分组）

**成果汇总**

| 路径 | 方法 | 作用 |
|------|------|------|
| `/achievements` | GET | 成果汇总页（奖状/专利/软著/大创/其他入口） |

说明：奖状相关路由（`/awards`、`/api/achievements/awards` 等）已迁移至 **admin_awards**，见下节。专利/软著/大创/其他 Tab API 在 `admin_patents`、`admin_software`、`admin_innovation`、`admin_other_files`，见下文各节。

**文件导入（核心）**

| 路径 | 方法 | 作用 |
|------|------|------|
| `/file-import` | GET | 文件导入上传页 |
| `/file-import/manual/upload` | POST | 手动导入：上传单文件到临时目录，返回 `file_path` |
| `/file-import/manual/parse` | POST | 手动导入：按类型解析文件，写 pending，返回 `redirect_url` |
| `/file-import/manual/submit` | POST | 手动导入：提交成果数据落库 |
| `/file-import/progress` | GET | 获取当前导入进度（session） |
| `/file-import/upload` | POST | 批量上传并解析（FileUploadService），写 pending，更新进度 |
| `/file-import/results` | GET | 导入结果页（按 session/类型/有效无效 Tab 展示） |
| `/file-import/file/<path:file_path>` | GET | 安全读取导入会话中的文件 |
| `/file-import/award-edit/<session_id>/<index>` | GET, POST | 单条奖状编辑（导入流程内） |
| `/file-import/review/<session_id>/<type>/<sub_tab>/<index>` | GET | 单条审核页（与成果审核共用 review_helpers） |
| `/file-import/api/list` | GET | 导入会话列表 API |
| `/file-import/api/stats` | GET | 导入统计 API |
| `/file-import/api/item/<id>` | GET | 单条导入项详情 API |
| `/file-import/api/submit` | POST | 提交导入项落库 |
| `/file-import/api/delete` | POST | 删除导入项 |
| `/file-import/api/other/submit` | POST | 其他类型文件提交 |
| `/file-import/award-submit/<session_id>/<index>` | POST | 单条奖状提交 |
| `/file-import/api/batch-import` | POST | 批量导入 |
| `/file-import/api/batch-discard` | POST | 批量丢弃 |

### 重要实现要点

- **file-import/upload**：使用 `FileUploadService`，从 `config.loader.get_config()` 取 `temp_dir`，在 `temp_dir/file_import_{session_id}` 下存文件；支持 OCR/LLM 缓存选项；解析结果写入 `PendingAchievementManager`，进度写入 `session['file_import_progress']`。
- **file-import/results（大创）**：大创按**文件**分页，每页一个 Excel；左侧为当前文件预览/下载，右侧为当前文件下 `achievement_data.projects` 的表格（#、项目编号、项目名称、年份、级别、负责人、指导教师、其他成员、验收等级、验证结果；无起止时间）。每行可「删除」「编辑」；「上一项/下一项」切换文件；「全部提交」「全部放弃」仅针对当前文件（传 `pending_ids: [当前文件 pending_id]`）。删除单行项目：`api/delete` 请求体 `tab_type=innovation`、`item_id`、`project_index`；编辑单行后提交：`api/submit` 请求体 `achievement_type=innovation`、`item_id`、`project_index` 及表单字段。大创文档在未归档前必须存在；仅当该文件下所有条目删除后才可删 Excel（`safe_delete_with_file`）。
- **file-import/api/delete**：支持 `item_id` 整条删除、`session_id+index` 按列表位置删除、以及大创单行删除：`tab_type=innovation` 且 `item_id`+`project_index`，从 `projects` 中移除该项，若 `projects` 为空则删除 pending 并删文件。
- **file-import/api/submit**：大创单项目编辑时请求体可带 `project_index`（或于 `data` 中），后端仅更新 `achievement_data.projects[project_index]` 后提交。
- **file-import/api/batch-import、api/batch-discard**：可选 `pending_ids`（列表）；若传入则仅处理这些 ID（大创按文件分页时仅提交/放弃当前文件）。
- **file-import/manual/parse**：支持类型 `award`/`patent`/`software`，调用 `ManualImportService(framework).parse_by_type(path, type, use_ocr_cache, use_llm_cache)`，成功后 `pending_manager.create_from_extract_result(...)` 并重定向到 results 页。
- **奖状编辑**：`awards/<id>/edit` 与导入流程内的 `file-import/award-edit/...` 共用业务逻辑，涉及竞赛关联、指导教师、学生名单等；刷新关联/指导教师由独立 POST 接口完成。
- **文件导入辅助**：成果类型配置、结果页参数、类型统计、pending 查询与奖状/非奖状项处理等逻辑在 `app/routes/file_import_helpers.py` 中，供本模块与审核流程复用。

---

## 四、admin_awards（admin_awards.py）— 奖状

| 路径 | 方法 | 作用 |
|------|------|------|
| `/awards` | GET | 奖状列表页（含异常 TAB、筛选、分页） |
| `/awards/<id>` | DELETE | 删除单条奖状 |
| `/awards/batch-delete` | POST | 批量删除奖状 |
| `/awards/<id>/image` | GET | 奖状图片流 |
| `/awards/refresh-associations` | POST | 刷新奖状与竞赛关联 |
| `/awards/refresh-supervisors` | POST | 刷新指导教师信息 |
| `/awards/<id>/edit` | GET, POST | 奖状编辑页与保存 |
| `/api/achievements/awards` | GET | 成果汇总页奖状 Tab 数据 API |
| `/api/awards/link-teacher-student` | POST | 奖状关联教师/学生 |

**实现要点**：奖状列表支持异常奖状 TAB、竞赛/年份/等级/实验室等筛选；编辑页支持管理员与教师（教师仅可编辑本人关联奖状）；图片流需登录且教师仅可访问本人关联奖状。

---

## 五、admin_export（admin_export.py）— 数据导出

| 路径 | 方法 | 作用 |
|------|------|------|
| `/data_export` | GET | 导出入口，重定向到系年度总结 |
| `/data_export/department_summary` | GET | 系年度总结页：按日期/年份筛选奖状，展示统计与列表 |
| `/data_export/department_summary/export` | POST | 导出系年度总结（如 Excel） |
| `/data_export/student_affairs` | GET | 学工相关导出入口页 |
| `/data_export/teacher_personal` | GET | 教师个人导出入口页 |

**实现要点**：系年度总结使用 `backend.utils.export_utils.generate_department_summary_data`、`format_date_to_month`，奖状查询排除教师证书、支持按年份与日期范围筛选。

---

## 六、admin_laboratory（admin_laboratory.py）— 实验室

| 路径 | 方法 | 作用 |
|------|------|------|
| `/laboratories` | GET | 实验室列表（含教师数、学生数、助理数） |
| `/laboratories/add` | GET, POST | 新建实验室 |
| `/laboratories/<id>/edit` | GET, POST | 编辑实验室（含封面图上传） |
| `/laboratories/<id>` | GET | 实验室详情 |
| `/laboratories/<id>` | DELETE | 删除实验室 |
| `/laboratories/<id>/achievements` | GET | 实验室关联成果页 |
| `/laboratories/<id>/competitions` | GET | 实验室关联竞赛页 |
| `/laboratories/<id>/assistants/add` | POST | 添加助理（学生） |
| `/laboratories/<id>/assistants/<student_id>/remove` | DELETE | 移除助理 |
| `/laboratories/<id>/images/upload` | POST | 上传实验室图片 |
| `/laboratories/<id>/images/delete` | POST | 删除实验室图片 |
| `/laboratories/<id>/downloads/upload` | POST | 上传下载资源 |
| `/laboratories/<id>/downloads/<id>` | DELETE | 删除下载资源 |
| `/laboratories/<id>/downloads` | GET | 下载资源列表 |
| `/laboratories/<id>/downloads/<id>/file` | GET | 下载单个资源文件 |
| `/files/laboratory/<path:filename>` | GET | 实验室文件访问（按 filename） |
| `/laboratory-downloads/<file_id>/download` | GET | 按 file_id 下载 |
| `/laboratory-downloads/<file_id>/delete` | POST | 按 file_id 删除 |

**实现要点**：封面图保存在 `static/images/laboratory_covers/`；实验室图片与下载资源由 `LaboratoryManager` 及关联表管理，路径通过配置或统一 file 服务获取，禁止硬编码。

---

## 七、admin_templates（admin_templates.py）— 奖状模板

| 路径 | 方法 | 作用 |
|------|------|------|
| `/templates` | GET | 模板管理主页（列表/详情/创建/测试 Tab） |
| `/templates/image/<template_id>` | GET | 模板样本图 |
| `/templates/refresh` | POST | 刷新模板（从文档/配置同步） |
| `/templates/force-refresh` | POST | 强制刷新 |
| `/templates/<id>/delete` | POST | 删除模板 |
| `/templates/<id>/update` | POST | 更新模板字段 |
| `/templates/<id>/update-granted-role` | POST | 更新授予角色 |
| `/templates/<id>/generate-prompt` | POST | 生成 LLM 提示 |
| `/templates/create` | POST | 创建模板 |
| `/templates/<id>/test` | POST | 测试模板（含 `/templates/0/test` 自动匹配） |
| `/api/validation-rules/<template_id>` | POST | 提交并返回校验规则 |

**实现要点**：通过 `get_doc_rec_context().template_manager` 获取 `TemplateManager`，模板类型为 `award`；使用 `TemplateAdapter` 将 document_extract 的 Template 适配为页面所需结构；模板数据与竞赛关联、base_fields 来自配置。

---

## 八、admin_patents（admin_patents.py）— 专利

| 路径 | 方法 | 作用 |
|------|------|------|
| `/patents` | GET | 专利列表（分页、类型/发明人/实验室筛选） |
| `/patents/<id>` | GET | 专利详情 |
| `/patents/create` | GET, POST | 创建专利 |
| `/patents/<id>/edit` | GET, POST | 编辑专利 |
| `/patents/<id>/delete` | POST | 删除专利 |
| `/patents/<id>/file` | GET | 专利附件下载 |
| `/api/patents/check-duplicate` | POST | 查重 |
| `/api/achievements/patents` | GET | 成果汇总页专利 Tab 数据 API |
| `/patents/<id>` | DELETE | 删除专利（成果汇总页调用） |
| `/patents/batch-delete` | POST | 批量删除专利（成果汇总页调用） |

**实现要点**：使用 `PatentManager`、`PatentFilter`；列表页需要实验室列表、提交人姓名（学生/教师/管理员）等关联数据。

---

## 九、admin_software（admin_software.py）— 软著

| 路径 | 方法 | 作用 |
|------|------|------|
| `/software` | GET | 软著列表（分页、登记号/著作权人/实验室筛选） |
| `/api/achievements/software` | GET | 成果汇总页软著 Tab 数据 API |
| `/software/<id>` | GET | 软著详情 |
| `/software/<id>` | DELETE | 删除软著（成果汇总页调用） |
| `/software/create` | GET, POST | 创建软著 |
| `/software/<id>/edit` | GET, POST | 编辑软著 |
| `/software/<id>/delete` | POST | 删除软著 |
| `/software/<id>/file` | GET | 软著附件下载 |
| `/api/software/check-duplicate` | POST | 查重 |
| `/software/batch-delete` | POST | 批量删除 |

**实现要点**：使用 `SoftwareCopyrightManager`、`SoftwareCopyrightFilter`；与专利类似，需实验室、提交人等信息。

---

## 十、admin_innovation（admin_innovation.py）— 大创

| 路径 | 方法 | 作用 |
|------|------|------|
| `/innovation` | GET | 大创列表（分页、类型/状态/负责人/项目名/实验室/年份筛选） |
| `/api/achievements/innovation` | GET | 成果汇总页大创 Tab 数据 API |
| `/innovation/<id>` | GET | 大创详情（含成员、指导教师） |
| `/innovation/create` | GET, POST | 创建大创 |
| `/innovation/<id>/edit` | GET, POST | 编辑大创 |
| `/innovation/<id>/delete` | POST | 删除大创 |
| `/api/innovation/check-duplicate` | POST | 查重 |

**实现要点**：使用 `InnovationProjectManager`、`InnovationProjectFilter`；详情页通过 `load_project_with_associations` 恢复学生关联；仅管理员可提交大创。

---

## 十一、admin_review（admin_review.py）— 成果审核

| 路径 | 方法 | 作用 |
|------|------|------|
| `/achievement-review` | GET | 待审核列表入口，重定向到第一个有数据的类型 Tab（单页审核） |
| `/achievement-review/<type>/<sub_tab>/<index>` | GET | 单条审核页（按类型/有效无效/索引） |
| `/achievement-review/<pending_id>` | GET | 按 pending_id 的审核详情（兼容） |
| `/achievement-review/<pending_id>/approve` | POST | 通过 |
| `/achievement-review/<pending_id>/reject` | POST | 驳回 |
| `/api/achievement-review/<pending_id>/approve-with-data` | POST | 带数据通过（写入正式表并归档） |
| `/api/achievement-review/<pending_id>/validation` | GET | 获取该条校验结果 |
| `/api/achievement-review/batch-approve` | POST | 批量通过 |

**实现要点**：审核逻辑由 `ReviewService`/`Reviewer` 完成；待审数据来自 `PendingAchievementManager`；与文件导入审核共用 `review_helpers.render_review_page`、`query_pending_items` 等；自动归档配置从 `config` 同步到 `AutoArchiveConfigManager`，再交给 `ReviewService`。

---

## 十二、admin_other_files（admin_other_files.py）— 其他文件

| 路径 | 方法 | 作用 |
|------|------|------|
| `/other-files` | GET | 其他文件列表（分页、类型/是否图片/提交人/实验室筛选） |
| `/api/achievements/other` | GET | 成果汇总页「其他文件」Tab 数据 API（实验室下载文件） |
| `/other-files/<id>` | GET | 文件详情 |
| `/other-files/upload` | GET, POST | 上传其他文件 |
| `/other-files/<id>/download` | GET | 下载 |
| `/other-files/<id>/edit` | POST | 编辑元数据 |
| `/other-files/<id>/delete` | POST | 删除 |
| `/api/other-files/<id>/preview` | GET | 预览（如图片） |

**实现要点**：使用 `OtherFileManager`、`OtherFileFilter`；提交人、实验室等信息在详情与列表中展示。成果汇总页「其他」Tab 使用 `laboratory_downloads` 表数据。

---

## 十三、注意事项与约定

1. **`/settings` 与 `/settings/save`**：由 **admin.py** 提供；侧栏等链接使用 `url_for('admin.settings')`。
2. **`/api/validation-rules/<template_id>`**：由 **admin_templates** 提供。
3. **配置与路径**：所有临时目录、数据库路径、存储根目录等均来自 `config.loader.get_config()` 或 `app.utils.get_app_context_instance()`，禁止在路由层硬编码路径或 URL。
4. **依赖的公共模块**：`app.utils`（`get_app_context_instance`、`get_doc_rec_context`、`get_config`、`calculate_file_hash`）、`app.auth`（`require_role`、`require_role_api`）、`app.routes.file_import_helpers`（成果类型配置与文件导入结果页辅助）、`app.routes.review_helpers`（审核页渲染与查询）、各 backend Manager/Service。
5. **奖状相关模板**：模板中奖状列表/编辑/图片/刷新等链接应使用 `admin_awards.*`，例如：`admin_awards.awards_list`、`admin_awards.award_edit`、`admin_awards.award_image`、`admin_awards.awards_refresh_associations`、`admin_awards.awards_refresh_supervisors`。成果汇总页入口使用 `admin_achievement.achievements`，文件导入使用 `admin_achievement.file_import`。

---

## 测试验证

重构后已通过以下测试确认路由与模板引用正确：

- **tests/run_all_tests.py**：文件流转、页面渲染、路由完整性、首页渲染共 4 个套件全部通过。
- **tests/test_admin_blueprints_registered.py**：admin / admin_achievement / admin_awards / admin_laboratory / admin_export / admin_templates 蓝图及关键端点（含 `admin_awards.awards_list`、`admin_awards.award_edit`、`admin_awards.award_image`、`admin_achievement.achievements`、`admin_achievement.file_import` 等）存在且可解析。
- **tests/test_admin_settings_logic.py**：系统设置逻辑通过。
- **tests/test_routes_integrity.py**：所有模板中的 `url_for()` 端点均存在（奖状相关已统一为 `admin_awards.*`）。

---

*文档版本与代码对应：以当前 `app/routes/admin*.py` 及 `app/__init__.py` 注册为准。*
