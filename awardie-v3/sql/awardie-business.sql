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
