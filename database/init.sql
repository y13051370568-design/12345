-- 创建数据库
CREATE DATABASE IF NOT EXISTS ai4ml_community DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ai4ml_community;

-- 1. 用户表
CREATE TABLE `sys_user` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '用户唯一标识',
  `username` VARCHAR(50) NOT NULL COMMENT '用户名/账号',
  `password_hash` VARCHAR(255) NOT NULL COMMENT '加密存储的密码',
  `role` VARCHAR(20) NOT NULL DEFAULT 'ZERO_BASIS' COMMENT '角色: ZERO_BASIS, DEVELOPER, ADMIN',
  `api_token_limit` INT NOT NULL DEFAULT 1000000 COMMENT 'API Token 额度上限',
  `api_token_used` INT NOT NULL DEFAULT 0 COMMENT '已使用的 API Token 数量',
  `status` TINYINT NOT NULL DEFAULT 1 COMMENT '账号状态: 1(启用), 0(禁用)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统用户表';

-- 2. 数据集表
CREATE TABLE `ml_dataset` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '数据集唯一标识',
  `user_id` BIGINT NOT NULL COMMENT '上传者ID',
  `name` VARCHAR(100) NOT NULL COMMENT '数据集名称',
  `description` TEXT COMMENT '数据集描述',
  `file_path` VARCHAR(255) NOT NULL COMMENT '服务器存储路径',
  `file_size_kb` INT NOT NULL COMMENT '文件大小(KB)',
  `is_public` TINYINT NOT NULL DEFAULT 0 COMMENT '是否公开: 0(私有), 1(公开)',
  `audit_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '审核状态: PENDING, APPROVED, REJECTED',
  `tags` VARCHAR(255) COMMENT '分类标签(逗号分隔)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_dataset_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据集信息表';

-- 3. 智能建模任务表
CREATE TABLE `ml_task` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '任务唯一标识',
  `user_id` BIGINT NOT NULL COMMENT '任务创建者ID',
  `dataset_id` BIGINT NOT NULL COMMENT '关联的数据集ID',
  `source_workflow_id` BIGINT DEFAULT NULL COMMENT '来源工作流ID，可为空',
  `task_description` TEXT NOT NULL COMMENT '自然语言任务描述',
  `task_type` VARCHAR(20) DEFAULT NULL COMMENT '任务类型: CLASSIFICATION, REGRESSION；解析完成后回填',
  `target_column` VARCHAR(100) DEFAULT NULL COMMENT '预测目标列名；解析完成后回填',
  `feature_columns_json` JSON DEFAULT NULL COMMENT '特征列列表，解析完成后回填',
  `status` VARCHAR(30) NOT NULL DEFAULT 'CREATED' COMMENT '状态: CREATED, RUNNING, WAITING_HUMAN, READY_TO_RESUME, COMPLETED, FAILED, CANCELLED',
  `current_node` VARCHAR(50) DEFAULT NULL COMMENT '当前待执行或待恢复的节点名',
  `version` INT NOT NULL DEFAULT 1 COMMENT '运行态版本号',
  `state_json` JSON DEFAULT NULL COMMENT '当前完整运行态JSON',
  `pending_review_json` JSON DEFAULT NULL COMMENT '当前待人工审核信息',
  `last_error_json` JSON DEFAULT NULL COMMENT '最近一次错误信息',
  `result_demo_url` VARCHAR(255) COMMENT 'Web Demo接口链接',
  `report_url` VARCHAR(255) COMMENT '模型分析报告链接',
  `fail_reason` TEXT COMMENT '失败原因记录',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  `started_at` DATETIME DEFAULT NULL COMMENT '任务开始执行时间',
  `finished_at` DATETIME DEFAULT NULL COMMENT '任务结束时间',
  PRIMARY KEY (`id`),
  KEY `idx_task_status_current_node` (`status`, `current_node`),
  KEY `idx_task_source_workflow` (`source_workflow_id`),
  CONSTRAINT `fk_task_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_task_dataset` FOREIGN KEY (`dataset_id`) REFERENCES `ml_dataset` (`id`) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智能建模任务流转表';

-- 4. 模型广场资源表
CREATE TABLE `ml_model` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '模型唯一标识',
  `task_id` BIGINT NOT NULL COMMENT '来源训练任务ID',
  `user_id` BIGINT NOT NULL COMMENT '模型所有者ID',
  `name` VARCHAR(100) NOT NULL COMMENT '模型名称',
  `description` TEXT COMMENT '模型描述',
  `task_type` VARCHAR(20) DEFAULT NULL COMMENT '模型对应任务类型',
  `target_column` VARCHAR(100) DEFAULT NULL COMMENT '模型对应目标列',
  `feature_columns_json` JSON DEFAULT NULL COMMENT '模型训练使用的特征列列表',
  `framework` VARCHAR(50) DEFAULT NULL COMMENT '训练框架，如 sklearn',
  `performance_metrics` JSON COMMENT '模型性能指标(准确率/MSE等)',
  `model_artifact_path` VARCHAR(255) DEFAULT NULL COMMENT '模型产物存储路径',
  `is_public` TINYINT NOT NULL DEFAULT 0 COMMENT '是否公开: 0(私有), 1(公开)',
  `audit_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '审核状态: PENDING, APPROVED, REJECTED',
  `is_recommended` TINYINT NOT NULL DEFAULT 0 COMMENT '是否被设为推荐: 0(否), 1(是)',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_model_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_model_task` FOREIGN KEY (`task_id`) REFERENCES `ml_task` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模型成果资源表';

-- 5. 开发者工作流表
CREATE TABLE `ml_workflow` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '工作流唯一标识',
  `user_id` BIGINT NOT NULL COMMENT '工作流所有者ID',
  `task_id` BIGINT NOT NULL COMMENT '来源任务ID',
  `title` VARCHAR(100) NOT NULL COMMENT '工作流标题',
  `description` TEXT COMMENT '工作流描述',
  `workflow_spec_json` JSON DEFAULT NULL COMMENT '工作流定义/节点与路由配置JSON',
  `default_config_json` JSON DEFAULT NULL COMMENT '默认配置JSON，如候选模型、HITL配置等',
  `prompt_template_json` JSON DEFAULT NULL COMMENT '提示词模板JSON，可为空',
  `applicable_task_types` VARCHAR(100) DEFAULT NULL COMMENT '适用任务类型列表，如 REGRESSION,CLASSIFICATION',
  `code_content` LONGTEXT NOT NULL COMMENT '干预后的完整Python代码',
  `fork_from_id` BIGINT DEFAULT NULL COMMENT 'Fork来源的工作流ID(如为原创则为NULL)',
  `is_public` TINYINT NOT NULL DEFAULT 0 COMMENT '是否公开: 0(私有), 1(公开)',
  `audit_status` VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '审核状态: PENDING, APPROVED, REJECTED',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_workflow_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_workflow_task` FOREIGN KEY (`task_id`) REFERENCES `ml_task` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='开发者工作流与代码共享表';

-- 6. 社区评价与评论表
CREATE TABLE `community_comment` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '评论记录ID',
  `user_id` BIGINT NOT NULL COMMENT '评论人ID',
  `resource_id` BIGINT NOT NULL COMMENT '被评价的资源ID',
  `resource_type` VARCHAR(20) NOT NULL COMMENT '资源类型: DATASET, MODEL, WORKFLOW',
  `rating` INT NOT NULL COMMENT '评分 (1-5)',
  `content` TEXT COMMENT '评论内容',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '评价时间',
  PRIMARY KEY (`id`),
  CONSTRAINT `fk_comment_user` FOREIGN KEY (`user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='社区资源评价交互表';

-- 7. 人机协同审核记录表
CREATE TABLE `ml_task_review` (
  `id` BIGINT NOT NULL AUTO_INCREMENT COMMENT '审核记录ID',
  `task_id` BIGINT NOT NULL COMMENT '关联任务ID',
  `operator_user_id` BIGINT NOT NULL COMMENT '执行审核/干预的用户ID',
  `review_stage` VARCHAR(50) NOT NULL COMMENT '审核阶段，如 parse_review/train_review',
  `action` VARCHAR(30) NOT NULL COMMENT '动作: approve, edit_and_continue, reject, send_back',
  `patch_json` JSON DEFAULT NULL COMMENT '人工修改补丁内容',
  `comment` TEXT COMMENT '审核备注',
  `before_version` INT DEFAULT NULL COMMENT '审核前版本号',
  `after_version` INT DEFAULT NULL COMMENT '审核后版本号',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '审核时间',
  PRIMARY KEY (`id`),
  KEY `idx_review_task` (`task_id`),
  KEY `idx_review_operator` (`operator_user_id`),
  CONSTRAINT `fk_task_review_task` FOREIGN KEY (`task_id`) REFERENCES `ml_task` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_task_review_user` FOREIGN KEY (`operator_user_id`) REFERENCES `sys_user` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='人机协同审核记录表';
