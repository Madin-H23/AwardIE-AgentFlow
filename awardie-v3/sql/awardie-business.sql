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
