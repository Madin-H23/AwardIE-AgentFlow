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
