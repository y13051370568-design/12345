-- ============================================================
-- AuditLog 字段类型修复迁移脚本
-- 用途：将 old_status/new_status 从 INT 改为 VARCHAR(50)
--       以支持 workflow 的字符串类型审核状态
-- 日期：2026-05-18
-- 执行前请备份数据库
-- ============================================================

USE ai4ml_community;

ALTER TABLE `audit_logs`
    MODIFY COLUMN `old_status` VARCHAR(50) DEFAULT NULL COMMENT '审核前状态',
    MODIFY COLUMN `new_status` VARCHAR(50) DEFAULT NULL COMMENT '审核后状态';
