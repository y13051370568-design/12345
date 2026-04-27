-- MySQL dump 10.13  Distrib 8.0.26, for Linux (x86_64)
--
-- Host: localhost    Database: ai4ml_community
-- ------------------------------------------------------
-- Server version	8.0.26

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `ai_models`
--

DROP TABLE IF EXISTS `ai_models`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ai_models` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `category` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tags` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` int DEFAULT NULL,
  `is_public` tinyint(1) DEFAULT NULL,
  `is_recommended` tinyint(1) DEFAULT NULL,
  `rejection_reason` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `resource_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_ai_models_id` (`id`),
  CONSTRAINT `ai_models_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `audit_logs`
--

DROP TABLE IF EXISTS `audit_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `audit_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `resource_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `resource_id` bigint NOT NULL,
  `admin_id` bigint NOT NULL,
  `old_status` int DEFAULT NULL,
  `new_status` int DEFAULT NULL,
  `action` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `reason` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `admin_id` (`admin_id`),
  KEY `ix_audit_logs_id` (`id`),
  CONSTRAINT `audit_logs_ibfk_1` FOREIGN KEY (`admin_id`) REFERENCES `sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ml_dataset`
--

DROP TABLE IF EXISTS `ml_dataset`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ml_dataset` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '数据集唯一标识',
  `user_id` bigint NOT NULL COMMENT '上传者ID',
  `name` varchar(100) NOT NULL COMMENT '数据集名称',
  `description` text COMMENT '数据集描述',
  `file_path` varchar(255) NOT NULL COMMENT '服务器存储路径',
  `file_size_kb` int NOT NULL COMMENT '文件大小(KB)',
  `is_public` tinyint NOT NULL DEFAULT '0' COMMENT '是否公开: 0(私有), 1(公开)',
  `audit_status` varchar(20) NOT NULL DEFAULT 'PENDING' COMMENT '审核状态: PENDING, APPROVED, REJECTED',
  `tags` varchar(255) DEFAULT NULL COMMENT '分类标签(逗号分隔)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  PRIMARY KEY (`id`),
  KEY `fk_dataset_user` (`user_id`),
  CONSTRAINT `fk_dataset_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='数据集信息表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ml_datasets`
--

DROP TABLE IF EXISTS `ml_datasets`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ml_datasets` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `category` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `tags` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `status` int DEFAULT NULL,
  `is_public` tinyint(1) DEFAULT NULL,
  `rejection_reason` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_url` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `file_size` bigint DEFAULT NULL,
  `row_count` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `updated_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_ml_datasets_id` (`id`),
  CONSTRAINT `ml_datasets_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ml_model`
--

DROP TABLE IF EXISTS `ml_model`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ml_model` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '模型唯一标识',
  `task_id` bigint NOT NULL COMMENT '来源训练任务ID',
  `user_id` bigint NOT NULL COMMENT '模型所有者ID',
  `name` varchar(100) NOT NULL COMMENT '模型名称',
  `description` text COMMENT '模型描述',
  `task_type` varchar(20) DEFAULT NULL COMMENT '模型对应任务类型',
  `target_column` varchar(100) DEFAULT NULL COMMENT '模型对应目标列',
  `feature_columns_json` json DEFAULT NULL COMMENT '模型训练使用的特征列列表',
  `framework` varchar(50) DEFAULT NULL COMMENT '训练框架，如 sklearn',
  `performance_metrics` json DEFAULT NULL COMMENT '模型性能指标(准确率/MSE等)',
  `model_artifact_path` varchar(255) DEFAULT NULL COMMENT '模型产物存储路径',
  `is_public` tinyint NOT NULL DEFAULT '0' COMMENT '是否公开: 0(私有), 1(公开)',
  `audit_status` varchar(20) NOT NULL DEFAULT 'PENDING' COMMENT '审核状态: PENDING, APPROVED, REJECTED',
  `is_recommended` tinyint NOT NULL DEFAULT '0' COMMENT '是否被设为推荐: 0(否), 1(是)',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  KEY `fk_model_user` (`user_id`),
  KEY `fk_model_task` (`task_id`),
  CONSTRAINT `fk_model_task` FOREIGN KEY (`task_id`) REFERENCES `ml_task` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_model_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='模型成果资源表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ml_task`
--

DROP TABLE IF EXISTS `ml_task`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ml_task` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '任务唯一标识',
  `user_id` bigint NOT NULL COMMENT '任务创建者ID',
  `dataset_id` bigint NOT NULL COMMENT '关联的数据集ID',
  `source_workflow_id` bigint DEFAULT NULL COMMENT '来源工作流ID，可为空',
  `task_description` text NOT NULL COMMENT '自然语言任务描述',
  `task_type` varchar(20) DEFAULT NULL COMMENT '任务类型: CLASSIFICATION, REGRESSION；解析完成后回填',
  `target_column` varchar(100) DEFAULT NULL COMMENT '预测目标列名；解析完成后回填',
  `feature_columns_json` json DEFAULT NULL COMMENT '特征列列表，解析完成后回填',
  `status` varchar(30) NOT NULL DEFAULT 'CREATED' COMMENT '状态: CREATED, RUNNING, WAITING_HUMAN, READY_TO_RESUME, COMPLETED, FAILED, CANCELLED',
  `current_node` varchar(50) DEFAULT NULL COMMENT '当前待执行或待恢复的节点名',
  `version` int NOT NULL DEFAULT '1' COMMENT '运行态版本号',
  `state_json` json DEFAULT NULL COMMENT '当前完整运行态JSON',
  `pending_review_json` json DEFAULT NULL COMMENT '当前待人工审核信息',
  `last_error_json` json DEFAULT NULL COMMENT '最近一次错误信息',
  `result_demo_url` varchar(255) DEFAULT NULL COMMENT 'Web Demo接口链接',
  `report_url` varchar(255) DEFAULT NULL COMMENT '模型分析报告链接',
  `fail_reason` text COMMENT '失败原因记录',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `started_at` datetime DEFAULT NULL COMMENT '任务开始执行时间',
  `finished_at` datetime DEFAULT NULL COMMENT '任务结束时间',
  PRIMARY KEY (`id`),
  KEY `fk_task_user` (`user_id`),
  KEY `fk_task_dataset` (`dataset_id`),
  CONSTRAINT `fk_task_dataset` FOREIGN KEY (`dataset_id`) REFERENCES `ml_dataset` (`id`) ON DELETE RESTRICT,
  CONSTRAINT `fk_task_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='智能建模任务流转表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `ml_task_review`
--

DROP TABLE IF EXISTS `ml_task_review`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `ml_task_review` (
  `id` bigint NOT NULL AUTO_INCREMENT COMMENT '审核记录ID',
  `task_id` bigint NOT NULL COMMENT '关联任务ID',
  `operator_user_id` bigint NOT NULL COMMENT '执行审核/干预的用户ID',
  `review_stage` varchar(50) NOT NULL COMMENT '审核阶段，如 parse_review/train_review',
  `action` varchar(30) NOT NULL COMMENT '动作: approve, edit_and_continue, reject, send_back',
  `patch_json` json DEFAULT NULL COMMENT '人工修改补丁内容',
  `comment` text COMMENT '审核备注',
  `before_version` int DEFAULT NULL COMMENT '审核前版本号',
  `after_version` int DEFAULT NULL COMMENT '审核后版本号',
  `created_at` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '审核时间',
  PRIMARY KEY (`id`),
  KEY `idx_review_task` (`task_id`),
  KEY `idx_review_operator` (`operator_user_id`),
  CONSTRAINT `fk_task_review_task` FOREIGN KEY (`task_id`) REFERENCES `ml_task` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_task_review_user` FOREIGN KEY (`operator_user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='人机协同审核记录表';
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `quota_logs`
--

DROP TABLE IF EXISTS `quota_logs`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `quota_logs` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` bigint NOT NULL,
  `tokens_consumed` int NOT NULL,
  `action` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `task_id` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `ix_quota_logs_id` (`id`),
  CONSTRAINT `quota_logs_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sys_user`
--

DROP TABLE IF EXISTS `sys_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sys_user` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `role` varchar(20) NOT NULL DEFAULT 'ZERO_BASIS',
  `api_token_limit` int DEFAULT '1000000',
  `api_token_used` int DEFAULT '0',
  `status` int DEFAULT '1',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `api_token_warning_threshold` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`),
  KEY `ix_sys_user_id` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-27 13:53:32
