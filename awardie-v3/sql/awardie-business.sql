-- ============================================================================
-- AwardIE 业务模块表结构(我们的迁移脚本;芋道不用 Flyway,SQL 脚本即真相)
-- 用法:官方 sql + awardie-cleanup.sql 之后,对本文件按批追加执行
-- 注意:所有字段必须写注释(芋道 codegen 导入表硬性要求,报 1001004009)
-- ============================================================================

-- ---- 批1:laboratories 实验室(首个垂直切片) ----
CREATE TABLE IF NOT EXISTS awardie_laboratories (
    id          BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    name        VARCHAR(200) NOT NULL COMMENT '实验室名称',
    description VARCHAR(500) DEFAULT NULL COMMENT '实验室描述',
    creator     VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater     VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted     BIT          DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id   BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 实验室表';

-- ---- 批2:用户域 schema 修正(芋道上游表的本 fork 调整,可重复执行) ----
-- 上游 system_users.password 为 varchar(100),装不下 v2 存量 werkzeug scrypt 哈希
-- ("scrypt:32768:8:1$16位salt$128位hex" ≈ 167 字符;BCrypt 仅 60)——批2 ETL 前置条件
ALTER TABLE system_users MODIFY COLUMN password VARCHAR(255) NOT NULL DEFAULT '' COMMENT '密码(scrypt 存量兼容加宽)';

-- ---- 批3:competitions 竞赛(字段对照 v2 PG competitions 11 业务列) ----
-- competition_name 唯一性由 service 层前置校验保证,**不加 DB 唯一索引**:
--   v3 为逻辑删除,唯一索引会让"已删同名"永久占位(无法重建),且服务层放行而 DB 抛
--   DuplicateKey 500,两层语义打架;竞赛名唯一规则落在 service(错误码显式友好)
-- 三个名单位为 BIT(1)(v2 BOOLEAN);is_auto_added 由 OCR 抽取链路标记
--   (v2 建档恒 false,列表页只展示"自动建/手工"标签)
CREATE TABLE IF NOT EXISTS awardie_competitions (
    id                       BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    competition_name         VARCHAR(200) NOT NULL COMMENT '竞赛名称',
    official_website         VARCHAR(500) DEFAULT NULL COMMENT '官网地址',
    organizer                VARCHAR(200) DEFAULT NULL COMMENT '主办方',
    competition_time         VARCHAR(100) DEFAULT NULL COMMENT '竞赛时间(如 4-10月)',
    participant_requirements TEXT         DEFAULT NULL COMMENT '参赛要求',
    grade_category           VARCHAR(50)  DEFAULT NULL COMMENT '组别类别',
    brief_description        TEXT         DEFAULT NULL COMMENT '简介',
    alias_list               TEXT         DEFAULT NULL COMMENT '别名列表(换行分隔)',
    white_list               BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否白名单',
    watch_list               BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否观察名单',
    is_auto_added            BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否自动创建',
    creator                  VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time              DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater                  VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time              DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted                  BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id                BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 竞赛表';

-- ---- 批4:pending_achievements 待审成果(提交流纵切面核心表,列对照 v2 20 列) ----
-- achievement_data/validation_result/llm_response/ext_info 用 JSON(v2 为 JSONB)
-- file_hash **不加 DB 唯一索引**:去重只对 status='pending' 生效(v2 语义:驳回后可重新提交),
--   唯一索引会误伤 archived/rejected 行,且逻辑删除下已删行永久占位;唯一性在 service 层
-- reviewer_*/review_time/review_comment/ocr_text/llm_*/session_id/assigned_reviewer_type
--   为批5 审核流与批7 AI 抽取预留,本批提交侧只写前半部分
CREATE TABLE IF NOT EXISTS awardie_pending_achievements (
    id                       BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    achievement_type         VARCHAR(20)  NOT NULL COMMENT '成果类型(award/patent/software/innovation/other)',
    achievement_data         JSON         NOT NULL COMMENT '结构化成果字段(15 字段等)',
    validation_result        JSON         DEFAULT NULL COMMENT '校验结果(is_valid/content_issues/completeness_issues)',
    submitter_type           VARCHAR(20)  NOT NULL COMMENT '提交人类型(student/teacher/admin)',
    submitter_id             BIGINT       DEFAULT NULL COMMENT '提交人编号',
    submit_time              DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
    status                   VARCHAR(20)  DEFAULT 'pending' NOT NULL COMMENT '状态(pending/archived/rejected)',
    reviewer_id              BIGINT       DEFAULT NULL COMMENT '审核人编号',
    review_time              DATETIME     DEFAULT NULL COMMENT '审核时间',
    review_comment           TEXT         DEFAULT NULL COMMENT '审核意见',
    file_path                VARCHAR(500) DEFAULT NULL COMMENT '文件相对路径',
    assigned_reviewer_type   VARCHAR(20)  DEFAULT NULL COMMENT '指派审核人类型(teacher/admin)',
    reviewer_type            VARCHAR(20)  DEFAULT NULL COMMENT '审核人类型(teacher/admin)',
    file_hash                VARCHAR(64)  NOT NULL DEFAULT '' COMMENT '文件 SHA-256(去重依据)',
    ocr_text                 TEXT         DEFAULT NULL COMMENT 'OCR 文本',
    llm_prompt               TEXT         DEFAULT NULL COMMENT 'LLM 提示词',
    llm_response             JSON         DEFAULT NULL COMMENT 'LLM 响应',
    ext_info                 JSON         DEFAULT NULL COMMENT '扩展信息',
    session_id               VARCHAR(50)  DEFAULT NULL COMMENT 'AI 会话编号',
    laboratory_id            BIGINT       DEFAULT NULL COMMENT '实验室编号',
    version                  INT          DEFAULT 1 NOT NULL COMMENT '版本号',
    creator                  VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time              DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater                  VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time              DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted                  BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id                BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 待审成果表';

-- ---- 批4:实验室关联四表(补批3 挂账;instructors/students 为关联表,无 deleted 列) ----
-- 说明:全部带 tenant_id(芋道租户拦截器对无 tenant_id 的表会跳过追加,导致跨租户可见)
CREATE TABLE IF NOT EXISTS awardie_laboratory_downloads (
    id            BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    laboratory_id BIGINT       NOT NULL COMMENT '实验室编号',
    file_path     VARCHAR(500) NOT NULL COMMENT '文件相对路径',
    file_title    VARCHAR(200) DEFAULT NULL COMMENT '文件标题',
    file_name     VARCHAR(200) DEFAULT NULL COMMENT '原始文件名',
    file_size     INT          DEFAULT NULL COMMENT '文件字节数',
    submitter_type VARCHAR(20) DEFAULT NULL COMMENT '提交人类型',
    submitter_id  BIGINT       DEFAULT NULL COMMENT '提交人编号',
    is_public     BIT(1)       DEFAULT b'1' NOT NULL COMMENT '是否公开',
    display_order INT          DEFAULT 0 NOT NULL COMMENT '显示顺序',
    creator       VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater       VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted       BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id     BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 实验室下载文件表';

CREATE TABLE IF NOT EXISTS awardie_laboratory_images (
    id            BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    laboratory_id BIGINT       NOT NULL COMMENT '实验室编号',
    image_path    VARCHAR(500) NOT NULL COMMENT '图片相对路径',
    file_name     VARCHAR(100) DEFAULT NULL COMMENT '原始文件名',
    file_hash     VARCHAR(64)  DEFAULT NULL COMMENT '文件 SHA-256',
    description   TEXT         DEFAULT NULL COMMENT '图片说明',
    display_order INT          DEFAULT 0 NOT NULL COMMENT '显示顺序',
    submitter_type VARCHAR(20) DEFAULT NULL COMMENT '提交人类型',
    submitter_id  BIGINT       DEFAULT NULL COMMENT '提交人编号',
    creator       VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time   DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater       VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time   DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted       BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id     BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 实验室图片表';

CREATE TABLE IF NOT EXISTS awardie_laboratory_instructors (
    laboratory_id BIGINT NOT NULL COMMENT '实验室编号',
    teacher_id    BIGINT NOT NULL COMMENT '教师编号',
    tenant_id     BIGINT DEFAULT 0 NOT NULL COMMENT '租户编号',
    PRIMARY KEY (laboratory_id, teacher_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 实验室教师关联表';

CREATE TABLE IF NOT EXISTS awardie_laboratory_students (
    laboratory_id BIGINT NOT NULL COMMENT '实验室编号',
    student_id    BIGINT NOT NULL COMMENT '学生编号',
    tenant_id     BIGINT DEFAULT 0 NOT NULL COMMENT '租户编号',
    PRIMARY KEY (laboratory_id, student_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 实验室学生关联表';

-- 1 提交 / 6 审核通过 / 7 驳回 / 8 物化入库)
-- 说明:四表只含 v2 物化所需列,批6 补编辑链字段(ALTER 扩展)

-- ---- achievement_audit_log 审核留痕 ----
CREATE TABLE IF NOT EXISTS awardie_achievement_audit_log (
    id               BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    achievement_id   BIGINT       NOT NULL COMMENT '待审成果编号',
    achievement_kind VARCHAR(20)  DEFAULT NULL COMMENT '成果类型(award/patent/software/innovation/other)',
    action_type      INT          NOT NULL COMMENT '动作码(1 提交/6 审核通过/7 驳回/8 物化入库)',
    action_result    INT          DEFAULT 0 NOT NULL COMMENT '动作结果(0/1/2)',
    operator_id      BIGINT       DEFAULT NULL COMMENT '操作人编号',
    operator_code    VARCHAR(64)  DEFAULT '' COMMENT '操作人账号',
    operator_name    VARCHAR(64)  DEFAULT '' COMMENT '操作人姓名',
    change_detail    JSON         DEFAULT NULL COMMENT '变更详情({"message","comment"})',
    remark           TEXT         DEFAULT NULL COMMENT '备注',
    creator          VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time      DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater          VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time      DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted          BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id        BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 成果审核留痕表';

-- ---- awards 获奖成果(approve 时物化;竞赛按名匹配,缺失自动建 is_auto_added) ----
CREATE TABLE IF NOT EXISTS awardie_awards (
    id                       BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    image_hash               VARCHAR(64)  DEFAULT NULL COMMENT '文件 SHA-256(与证书图一致)',
    certificate_id           VARCHAR(50)  DEFAULT NULL COMMENT '证书编号',
    certificate_path         VARCHAR(500) DEFAULT NULL COMMENT '证书文件相对路径',
    competition_name_in_file VARCHAR(200) DEFAULT NULL COMMENT '证书内竞赛名',
    track                    VARCHAR(100) DEFAULT NULL COMMENT '赛道',
    issuer                   VARCHAR(100) DEFAULT NULL COMMENT '颁发方',
    province                 VARCHAR(100) DEFAULT NULL COMMENT '省份',
    group_name               VARCHAR(100) DEFAULT NULL COMMENT '组别',
    winner_name              VARCHAR(100) DEFAULT NULL COMMENT '获奖人',
    supervisor_name          VARCHAR(100) DEFAULT NULL COMMENT '指导教师',
    award_level              VARCHAR(20)  DEFAULT NULL COMMENT '获奖等级',
    competition_level        VARCHAR(20)  DEFAULT NULL COMMENT '竞赛级别',
    date                     VARCHAR(10)  DEFAULT NULL COMMENT '获奖日期',
    project_title            VARCHAR(200) DEFAULT NULL COMMENT '项目名称',
    competition_id           BIGINT       DEFAULT NULL COMMENT '竞赛编号',
    submitter_type           VARCHAR(20)  DEFAULT NULL COMMENT '提交人类型',
    submitter_id             BIGINT       DEFAULT NULL COMMENT '提交人编号',
    submit_time              DATETIME     DEFAULT NULL COMMENT '提交时间',
    laboratory_id            BIGINT       DEFAULT NULL COMMENT '实验室编号(v2 同列,删除实验室的引用检查依赖它)',
    creator                  VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time              DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater                  VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time              DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted                  BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id                BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 获奖成果表';

-- ---- award_student_winners 学生获奖关联(批4 物化时建) ----
CREATE TABLE IF NOT EXISTS awardie_award_student_winners (
    id          BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    award_id    BIGINT       NOT NULL COMMENT '获奖成果编号',
    student_id  BIGINT       NOT NULL COMMENT '学生编号',
    creator     VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    deleted     BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id   BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号',
    UNIQUE KEY uk_award_student (award_id, student_id)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 获奖学生关联表';

-- ---- patents 专利 ----
CREATE TABLE IF NOT EXISTS awardie_patents (
    id                 BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    patent_name        VARCHAR(200) NOT NULL COMMENT '专利名称',
    patent_type        VARCHAR(20)  DEFAULT NULL COMMENT '专利类型(发明专利/实用新型/外观设计)',
    application_number VARCHAR(50)  DEFAULT NULL COMMENT '申请号',
    inventor           VARCHAR(200) DEFAULT NULL COMMENT '发明人',
    patentee           VARCHAR(200) DEFAULT NULL COMMENT '专利权人',
    certificate_file   VARCHAR(500) DEFAULT NULL COMMENT '证书文件相对路径',
    submitter_type     VARCHAR(20)  DEFAULT NULL COMMENT '提交人类型',
    submitter_id       BIGINT       DEFAULT NULL COMMENT '提交人编号',
    laboratory_id      BIGINT       DEFAULT NULL COMMENT '实验室编号',
    creator            VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time        DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater            VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time        DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted            BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id          BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号',
    UNIQUE KEY uk_patent_application_number (application_number)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 专利表';

-- ---- software_copyrights 软件著作权 ----
CREATE TABLE IF NOT EXISTS awardie_software_copyrights (
    id                  BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    software_name       VARCHAR(200) NOT NULL COMMENT '软件名称',
    software_version    VARCHAR(20)  DEFAULT NULL COMMENT '软件版本',
    registration_number VARCHAR(50)  DEFAULT NULL COMMENT '登记号',
    copyright_owner     VARCHAR(200) DEFAULT NULL COMMENT '著作权人',
    certificate_file    VARCHAR(500) DEFAULT NULL COMMENT '证书文件相对路径',
    submitter_type      VARCHAR(20)  DEFAULT NULL COMMENT '提交人类型',
    submitter_id        BIGINT       DEFAULT NULL COMMENT '提交人编号',
    submit_time         DATETIME     DEFAULT NULL COMMENT '提交时间',
    laboratory_id       BIGINT       DEFAULT NULL COMMENT '实验室编号',
    creator             VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time         DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater             VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time         DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted             BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id           BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号',
    UNIQUE KEY uk_software_registration_number (registration_number)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 软件著作权表';

-- ---- other_files 其他成果 ----
CREATE TABLE IF NOT EXISTS awardie_other_files (
    id             BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    file_name      VARCHAR(200) NOT NULL COMMENT '成果名称',
    file_path      VARCHAR(500) NOT NULL COMMENT '文件相对路径',
    file_hash      VARCHAR(64)  DEFAULT NULL COMMENT '文件 SHA-256',
    description    TEXT         DEFAULT NULL COMMENT '描述',
    submitter_type VARCHAR(20)  DEFAULT NULL COMMENT '提交人类型',
    submitter_id   BIGINT       DEFAULT NULL COMMENT '提交人编号',
    submit_time    DATETIME     DEFAULT NULL COMMENT '提交时间',
    laboratory_id  BIGINT       DEFAULT NULL COMMENT '实验室编号',
    creator        VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time    DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater        VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time    DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted        BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id      BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号',
    UNIQUE KEY uk_other_file_path (file_path)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 其他成果文件表';

-- 说明:awards/patents/software_copyrights/other_files 在批5 只建了物化所需列,
--       批6 按 v2 成果库(Fix-C/Fix-R/Fix-T)补齐列表/编辑所需列

-- ---- 批6 补列说明:MySQL 8 不支持 ADD COLUMN IF NOT EXISTS(MariaDB 语法)。
--      幂等由 scripts/run_awardie_sql.py 容忍'列已存在'(1060)保证;CI 每次全新库故天然无此问题 ----
-- ---- awards 补列(成果库列表用 year/is_abnormal,编辑链用组别/省份/参赛信息) ----
ALTER TABLE awardie_awards ADD COLUMN year INT NULL COMMENT '年份(列表筛选)', ADD COLUMN edition VARCHAR(50) NULL COMMENT '届次', ADD COLUMN related_student_name VARCHAR(100) NULL COMMENT '关联学生姓名', ADD COLUMN is_abnormal BIT(1) NOT NULL DEFAULT b'0' COMMENT '是否异常', ADD COLUMN ocr_result TEXT NULL COMMENT 'OCR 抽取结果', ADD COLUMN extract_json TEXT NULL COMMENT '结构化抽取 JSON', ADD COLUMN match_status BIT(1) NULL COMMENT '匹配状态';


-- ---- other_files 补列(列表用 file_type/file_size/is_image) ----
ALTER TABLE awardie_other_files ADD COLUMN file_type VARCHAR(20) NULL COMMENT '文件类型', ADD COLUMN file_size INT NULL COMMENT '文件字节数', ADD COLUMN is_image BIT(1) NOT NULL DEFAULT b'0' COMMENT '是否图片';


-- ---- software_copyrights 补列(编辑链:证书号/登记日期) ----
ALTER TABLE awardie_software_copyrights ADD COLUMN certificate_no VARCHAR(50) NULL COMMENT '证书号', ADD COLUMN registration_date VARCHAR(10) NULL COMMENT '登记日期';


-- ---- patents 补列(编辑链:公开号/申请日期) ----
ALTER TABLE awardie_patents ADD COLUMN publication_number VARCHAR(50) NULL COMMENT '公开号', ADD COLUMN application_date VARCHAR(10) NULL COMMENT '申请日期';


-- ---- 大创(innovation_projects):批5 不物化大创,本批建全表(批8 做 status 方向1+2) ----
CREATE TABLE IF NOT EXISTS awardie_innovation_projects (
    id                  BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    project_no          VARCHAR(50)  DEFAULT NULL COMMENT '项目编号',
    project_name        VARCHAR(200) NOT NULL COMMENT '项目名称',
    project_type        VARCHAR(20)  DEFAULT NULL COMMENT '项目类型(国家级/省级/院级)',
    start_date          VARCHAR(10)  DEFAULT NULL COMMENT '开始日期',
    end_date            VARCHAR(10)  DEFAULT NULL COMMENT '结束日期',
    student_leader_name VARCHAR(50)  DEFAULT NULL COMMENT '学生负责人',
    student_leader_id   VARCHAR(50)  DEFAULT NULL COMMENT '学生负责人学号',
    other_members       JSON         DEFAULT NULL COMMENT '其他成员(数组)',
    supervisors         TEXT         DEFAULT NULL COMMENT '指导教师',
    funding_amount      DECIMAL(12,2) DEFAULT NULL COMMENT '经费',
    status              VARCHAR(20)  DEFAULT '进行中' COMMENT '状态(进行中/已结题/终止)',
    submitter_type      VARCHAR(20)  DEFAULT NULL COMMENT '提交人类型',
    submitter_id        BIGINT       DEFAULT NULL COMMENT '提交人编号',
    submit_time         DATETIME     DEFAULT NULL COMMENT '提交时间',
    laboratory_id       BIGINT       DEFAULT NULL COMMENT '实验室编号',
    creator             VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time         DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater             VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time         DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted             BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id           BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号',
    UNIQUE KEY uk_innovation_project_no (project_no)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 大创项目表';

-- ---- 大创学生关联(成果库"我的大创"依赖) ----
-- 批8 补约束:v2 该表无主键约束外的任何完整性(无 FK、无唯一、无索引),
-- 导致重复关联无法防、删除项目不触发级联、查询全表扫。
-- 唯一键含 deleted:逻辑删除后允许重建同一条关联(沿项目"逻辑删除 + 唯一键共存"口径)。
CREATE TABLE IF NOT EXISTS awardie_innovation_project_students (
    id              BIGINT      PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    project_id      BIGINT      NOT NULL COMMENT '大创项目编号',
    student_id      BIGINT      DEFAULT NULL COMMENT '学生编号',
    role            VARCHAR(20) DEFAULT NULL COMMENT '角色(leader/member)',
    student_name    VARCHAR(50) DEFAULT NULL COMMENT '学生姓名',
    student_id_str  VARCHAR(50) DEFAULT NULL COMMENT '学号',
    match_type      VARCHAR(20) DEFAULT NULL COMMENT '匹配方式(student_id_exact 等)',
    creator         VARCHAR(64) DEFAULT '' COMMENT '创建者',
    create_time     DATETIME    DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    deleted         BIT(1)      DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id       BIGINT      DEFAULT 0 NOT NULL COMMENT '租户编号'
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 大创项目学生关联表';

-- 注意:MySQL 的 CREATE TABLE IF NOT EXISTS 对**已存在**的表不会补列/索引,
-- 故批6 已建过本表的环境必须再跑下面的 ALTER(重跑报 1061/1060 由 runner 容忍)。
-- 本段注释内禁用分号——run_awardie_sql.py 按分号切语句(批5 立的纪律,本批自己踩了一次)。
-- 批6 建表时本表缺 updater/update_time 两列,而 DO 继承 BaseDO(带这两字段),
-- insert 时 MyBatis-Plus 会带上它们 → 500 Unknown column。批8 补齐。
ALTER TABLE awardie_innovation_project_students
    ADD COLUMN updater VARCHAR(64) DEFAULT '' COMMENT '更新者',
    ADD COLUMN update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';
ALTER TABLE awardie_innovation_project_students
    ADD UNIQUE KEY uk_innovation_project_student (project_id, student_id, deleted),
    ADD KEY idx_innovation_students_student (student_id);

-- ---- 批8:大创项目表约束补齐 ----
-- funding_amount 列注释写明单位为"元":v2 导入页写"万元"、编辑页写"元"、后端不换算,
-- 同一数字在两处差 10000 倍。v3 统一为元,导入时按万元 ×10000 换算入库(换算只在导入边界发生一次)。
-- 其余列(项目类型/状态的枚举校验)走应用层,不建 DB CHECK(沿项目既有口径:逻辑删除下 CHECK 与
-- 业务枚举的配合易出静默失败;且 v2 的 CHECK 曾导致 DataIntegrityViolation 被误报成"编号已存在")。
-- 注意:本段注释内禁用分号——run_awardie_sql.py 按分号切语句(批5 立的纪律,本批自己踩了一次)。
ALTER TABLE awardie_innovation_projects
    MODIFY COLUMN funding_amount DECIMAL(12,2) DEFAULT NULL COMMENT '资助金额(单位:元,导入时按万元乘10000换算)';

-- ============================================================================
-- 批7 模板域(证书模板)
-- ============================================================================
-- 对照 v2 templates 表(16 字段)+ 批4 文件域收敛(样本图存相对路径而非 BYTEA)。
-- 相对 v2 的三处建模变更(均为修缺陷/补基础设施,语义见 docs 批7 01-spec 决策表):
--   1. 补芋道标准列 tenant_id/creator/create_time/updater/update_time/deleted
--      —— v2 无租户列、无逻辑删除,无法接入芋道租户拦截器与逻辑删除基础设施。
--   2. granted_role 提为独立列 —— v2 把它藏在 default_fields JSONB 里,唯一性
--      ("同竞赛+同角色只能一个模板")只能靠 JSON 取值比较,不可索引。且编辑时
--      default_fields 整体可写,可改掉 role 绕过唯一性,那是缺陷不是语义。
--   3. 规则字段用 MySQL JSON 类型 —— 与批4 validation_result / 批6 other_members 一致。
-- 不加 name/status/业务编号:v2 无此语义、无存量值可回填,凭空建模等于发明业务。
-- 唯一性不建 DB 索引(沿项目既定纪律):逻辑删除下唯一索引会误伤已删行。
-- competition_id 建索引:它是列表过滤维度,也是批3 COMPETITION_REFERENCES 已预留的
-- 竞赛删除保护依据(表一建成,该保护自动生效,无需改批3 代码)。
CREATE TABLE IF NOT EXISTS awardie_templates (
    id                BIGINT       PRIMARY KEY AUTO_INCREMENT COMMENT '主键',
    template_type     VARCHAR(20)  DEFAULT 'AWARD' COMMENT '模板类型(仅 AWARD 奖状)',
    competition_id    BIGINT       NOT NULL COMMENT '竞赛编号',
    granted_role      VARCHAR(20)  NOT NULL COMMENT '授予角色(学生/教师)',
    min_length        INT          DEFAULT 0 COMMENT '抽取文本最小长度(0=不限)',
    max_length        INT          DEFAULT 0 COMMENT '抽取文本最大长度(0=不限)',
    keywords          JSON         DEFAULT NULL COMMENT '关键词(字符串数组)',
    sample_text       TEXT         DEFAULT NULL COMMENT '样本文本(OCR 原文/参考文本)',
    sample_extracted  JSON         DEFAULT NULL COMMENT '样本抽取结果(对象)',
    default_fields    JSON         DEFAULT NULL COMMENT '默认字段(对象)',
    llm_fields        JSON         DEFAULT NULL COMMENT '交给 LLM 的字段(对象)',
    language          VARCHAR(10)  DEFAULT 'zh' COMMENT '输出语言',
    need_translate    BIT(1)       DEFAULT b'0' COMMENT '是否需要翻译',
    sample_image_path VARCHAR(500) DEFAULT NULL COMMENT '样本图相对路径(批4 文件域)',
    creator           VARCHAR(64)  DEFAULT '' COMMENT '创建者',
    create_time       DATETIME     DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updater           VARCHAR(64)  DEFAULT '' COMMENT '更新者',
    update_time       DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    deleted           BIT(1)       DEFAULT b'0' NOT NULL COMMENT '是否删除',
    tenant_id         BIGINT       DEFAULT 0 NOT NULL COMMENT '租户编号',
    KEY idx_templates_competition (competition_id),
    KEY idx_templates_comp_role (competition_id, granted_role)
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4 COMMENT = 'AwardIE 证书模板表';
