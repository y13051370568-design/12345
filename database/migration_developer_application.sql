-- ============================================================
-- 开发者申请功能数据库迁移脚本
-- 用途：零基础用户申请成为开发者的功能表
-- 日期：2026-05-18
-- 执行前请备份数据库
-- ============================================================

USE ai4ml_community;

-- 开发者申请表
CREATE TABLE IF NOT EXISTS `developer_application` (
    `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '申请唯一标识',
    `user_id` BIGINT NOT NULL COMMENT '申请人用户ID',
    `reason` TEXT COMMENT '申请理由（用户填写）',
    `status` VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '审核状态: PENDING(待审核), APPROVED(已通过), REJECTED(已驳回)',
    `reviewed_by` BIGINT DEFAULT NULL COMMENT '审核人用户ID',
    `review_comment` VARCHAR(255) DEFAULT NULL COMMENT '审核意见',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '申请时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    CONSTRAINT `fk_application_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE,
    CONSTRAINT `fk_application_reviewer` FOREIGN KEY (`reviewed_by`) REFERENCES `sys_user` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='开发者申请表';
