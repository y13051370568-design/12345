-- ============================================================
-- 社区功能数据库迁移脚本
-- 用途：为 community 分支新增字段执行 ALTER TABLE
-- 日期：2026-05-11
-- 执行前请备份数据库
-- ============================================================

USE ai4ml_community;

-- -----------------------------------------------------------
-- 1. ml_workflow（开发者工作流表）— 新增 7 个字段
--    对应 community 分支 AgentWorkflow 模型新增字段
-- -----------------------------------------------------------
ALTER TABLE `ml_workflow`
    ADD COLUMN `category`          VARCHAR(50)   DEFAULT NULL COMMENT '工作流分类'               AFTER `fork_from_id`,
    ADD COLUMN `tags`              VARCHAR(255)  DEFAULT NULL COMMENT '分类标签(逗号分隔)'        AFTER `category`,
    ADD COLUMN `view_count`        INT           DEFAULT 0    COMMENT '浏览量'                   AFTER `tags`,
    ADD COLUMN `fork_count`        INT           DEFAULT 0    COMMENT 'Fork 次数'                AFTER `view_count`,
    ADD COLUMN `is_recommended`    TINYINT       DEFAULT 0    COMMENT '是否推荐: 0(否), 1(是)'   AFTER `fork_count`,
    ADD COLUMN `rejection_reason`  VARCHAR(255)  DEFAULT NULL COMMENT '驳回原因'                  AFTER `is_recommended`,
    ADD COLUMN `updated_at`        DATETIME      DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间' AFTER `rejection_reason`;

-- -----------------------------------------------------------
-- 2. ml_datasets（数据中心资源表）— 新增 1 个字段
--    对应 community 分支 Dataset 模型新增字段
-- -----------------------------------------------------------
ALTER TABLE `ml_datasets`
    ADD COLUMN `view_count` INT DEFAULT 0 COMMENT '浏览量' AFTER `is_public`;

-- -----------------------------------------------------------
-- 3. ai_models（AI 模型资源表）— 新增 1 个字段
--    对应 community 分支 AIModel 模型新增字段
-- -----------------------------------------------------------
ALTER TABLE `ai_models`
    ADD COLUMN `view_count` INT DEFAULT 0 COMMENT '浏览量' AFTER `is_recommended`;
