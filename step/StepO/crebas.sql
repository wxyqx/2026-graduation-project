/*==============================================================*/
/* ATS 招聘管理系统 建表脚本（v3.15，12 张表）                    */
/*                                                              */
/* 适用：MySQL 8.x，字符集 utf8mb4，库名 ats                      */
/* 用法：                                                       */
/*   CREATE DATABASE IF NOT EXISTS ats DEFAULT CHARSET utf8mb4;  */
/*   mysql -u root -p ats < crebas.sql                           */
/*                                                              */
/* 已有 v3.14 数据库请勿执行本脚本，改用：                        */
/*   migrate_v3.15_three_portal.sql                              */
/*                                                              */
/* 说明：v3.15 在原有 6 张表上增加 6 张表：                       */
/*   Candidate_File  候选人文件（BLOB 入库）                      */
/*   Form_Template   表单模板                                    */
/*   Form_Field      表单字段                                    */
/*   Form_Submission 表单答卷                                    */
/*   Form_Answer     表单答案                                    */
/*   Operation_Log   操作日志                                    */
/*==============================================================*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS `Form_Answer`;
DROP TABLE IF EXISTS `Form_Submission`;
DROP TABLE IF EXISTS `Form_Field`;
DROP TABLE IF EXISTS `Form_Template`;
DROP TABLE IF EXISTS `Candidate_File`;
DROP TABLE IF EXISTS `Operation_Log`;
DROP TABLE IF EXISTS `Application`;
DROP TABLE IF EXISTS `AI_API_Config`;
DROP TABLE IF EXISTS `App_Setting`;
DROP TABLE IF EXISTS `User`;
DROP TABLE IF EXISTS `Candidate`;
DROP TABLE IF EXISTS `Position`;

SET FOREIGN_KEY_CHECKS = 1;

/*==============================================================*/
/* Table: Position（岗位）                                       */
/*==============================================================*/
CREATE TABLE `Position` (
  `ID`                    INT NOT NULL AUTO_INCREMENT,
  `position_name`         VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '岗位名称',
  `owner`                 VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '负责人',
  `position_requirements` VARCHAR(2000) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '岗位要求/JD，AI 筛选的比对依据',
  `is_hidden`             TINYINT DEFAULT 0 COMMENT '1=暂不招（隐藏），数据保留',
  PRIMARY KEY (`ID`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='招聘岗位';

/*==============================================================*/
/* Table: Candidate（候选人）                                    */
/*==============================================================*/
CREATE TABLE `Candidate` (
  `ID`          INT NOT NULL AUTO_INCREMENT,
  `create_time` DATETIME DEFAULT NULL COMMENT '录入时间',
  `name`        VARCHAR(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '姓名',
  `phone`       VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '手机号：候选人端登录账号，唯一',
  `email`       VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '邮箱（可空，不做验证）',
  `remark`          VARCHAR(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '备注',
  `onboard_date`    VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '到岗时间（HR 从简历摘录，可写「随时」等）',
  `school`          VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '毕业院校',
  `degree`          VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '学历（大专/本科/硕士/博士/其他）',
  `major`           VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '专业',
  `expected_salary` VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '期望薪资',
  `work_location`   VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '期望工作地点',
  `hire_type`       VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '招聘类型（校招/社招）',
  `work_experience` TEXT COLLATE utf8mb4_unicode_ci COMMENT '工作经历（HR 从简历摘录）',
  `update_time`     DATETIME DEFAULT NULL COMMENT '最近更新时间',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_Candidate_Phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='候选人基础信息';

/*==============================================================*/
/* Table: User（账号：HR / 技术管理员 / 候选人）                  */
/*==============================================================*/
CREATE TABLE `User` (
  `ID`             INT NOT NULL AUTO_INCREMENT,
  `username`       VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'HR/技术管理员用户名；候选人账号为 NULL',
  `password_hash`  VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT 'bcrypt 密码哈希',
  `role`           VARCHAR(20) NOT NULL DEFAULT 'hr' COMMENT 'candidate=候选人 / hr=HR / admin=技术管理员',
  `candidate_id`   INT DEFAULT NULL COMMENT '候选人账号关联的 Candidate.ID',
  `is_active`      TINYINT NOT NULL DEFAULT 1 COMMENT '0=停用，禁止登录',
  `last_login_time` DATETIME DEFAULT NULL COMMENT '最近登录时间',
  `last_login_ip`  VARCHAR(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '最近登录 IP',
  `Avatar`         LONGBLOB COMMENT '头像图片内容；NULL=未设置',
  `Avatar_Mime`    VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '头像 MIME 类型',
  `create_time`    DATETIME DEFAULT NULL COMMENT '创建时间',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `AK_Username_UK` (`username`),
  UNIQUE KEY `UK_User_Candidate` (`candidate_id`),
  CONSTRAINT `FK_User_Candidate` FOREIGN KEY (`candidate_id`) REFERENCES `Candidate` (`ID`)
      ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='三个端共用的登录账号';

/*==============================================================*/
/* Table: Application（投递，核心业务表）                        */
/*==============================================================*/
CREATE TABLE `Application` (
  `ID`                 INT NOT NULL AUTO_INCREMENT,
  `Can_ID`             INT NOT NULL COMMENT '候选人编号',
  `Pos_ID`             INT NOT NULL COMMENT '岗位编号',
  `ai_result`          VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'AI筛选结果 pass/fail',
  `resume_submit_time` DATETIME DEFAULT NULL COMMENT '简历提交时间',
  `resume_result`      VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '简历筛选结果',
  `phone_time`         DATETIME DEFAULT NULL COMMENT '电话沟通时间',
  `phone_result`       VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '电话沟通结果',
  `test_time`          DATETIME DEFAULT NULL COMMENT '笔试时间',
  `test_result`        VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '笔试结果',
  `pro_time`           DATETIME DEFAULT NULL COMMENT '专业面时间',
  `pro_result`         VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '专业面结果',
  `hr_time`            DATETIME DEFAULT NULL COMMENT 'HR面时间',
  `hr_result`          VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'HR面结果',
  `final_time`         DATETIME DEFAULT NULL COMMENT '终面时间',
  `final_result`       VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '终面结果',
  `current_stage`      VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '当前阶段 ai/resume/phone/test/pro/hr/final',
  `overall_status`     VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending' COMMENT 'pending/pass/fail',
  `ai_comment`         VARCHAR(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT 'AI筛选理由',
  `resume_reason`      TEXT COLLATE utf8mb4_unicode_ci COMMENT '简历筛选原因',
  `phone_reason`       TEXT COLLATE utf8mb4_unicode_ci COMMENT '电话沟通原因',
  `phone_evaluation`   TEXT COLLATE utf8mb4_unicode_ci COMMENT '电话沟通面试评价',
  `test_reason`        TEXT COLLATE utf8mb4_unicode_ci COMMENT '笔试原因',
  `pro_reason`         TEXT COLLATE utf8mb4_unicode_ci COMMENT '专业面原因',
  `pro_evaluation`     TEXT COLLATE utf8mb4_unicode_ci COMMENT '专业面面试评价',
  `hr_reason`          TEXT COLLATE utf8mb4_unicode_ci COMMENT 'HR面原因',
  `hr_evaluation`      TEXT COLLATE utf8mb4_unicode_ci COMMENT 'HR面面试评价',
  `final_reason`       TEXT COLLATE utf8mb4_unicode_ci COMMENT '终面原因',
  `final_evaluation`   TEXT COLLATE utf8mb4_unicode_ci COMMENT '终面面试评价',
  `source`             VARCHAR(20) NOT NULL DEFAULT 'admin' COMMENT 'admin=HR手动 / ai_intake=AI录入 / portal=候选人自主投递',
  `create_time`        DATETIME DEFAULT NULL COMMENT '投递创建时间',
  `update_time`        DATETIME DEFAULT NULL COMMENT '最近更新时间',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_Can_Pos` (`Can_ID`, `Pos_ID`),
  KEY `FK_Relationship_1` (`Pos_ID`),
  KEY `FK_Relationship_2` (`Can_ID`),
  CONSTRAINT `FK_Relationship_1` FOREIGN KEY (`Pos_ID`) REFERENCES `Position` (`ID`)
      ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `FK_Relationship_2` FOREIGN KEY (`Can_ID`) REFERENCES `Candidate` (`ID`)
      ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='候选人与岗位的投递关系，记录 7 关结果与时间';

/*==============================================================*/
/* Table: AI_API_Config（AI 接口配置）                            */
/*==============================================================*/
CREATE TABLE `AI_API_Config` (
  `ID`         INT NOT NULL AUTO_INCREMENT,
  `name`       VARCHAR(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '配置名称',
  `base_url`   VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '接口地址',
  `api_key`    VARCHAR(255) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '密钥（自用系统明文存储）',
  `model`      VARCHAR(100) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '模型名',
  `is_enabled` TINYINT DEFAULT 0 COMMENT '1=启用',
  `User_ID`    INT NOT NULL COMMENT '创建/维护人',
  PRIMARY KEY (`ID`),
  KEY `FK_Relationship_3` (`User_ID`),
  CONSTRAINT `FK_Relationship_3` FOREIGN KEY (`User_ID`) REFERENCES `User` (`ID`)
      ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='AI 筛选使用的 LLM 配置';

/*==============================================================*/
/* Table: App_Setting（系统设置键值对）                           */
/*==============================================================*/
CREATE TABLE `App_Setting` (
  `ID`            INT NOT NULL AUTO_INCREMENT,
  `User_ID`       INT NOT NULL COMMENT '所属用户',
  `setting_key`   VARCHAR(50) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '设置项，如 ai_prompt / stage_notes',
  `setting_value` TEXT COLLATE utf8mb4_unicode_ci COMMENT '设置内容',
  `update_time`   DATETIME DEFAULT NULL COMMENT '更新时间',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_User_Key` (`User_ID`, `setting_key`),
  CONSTRAINT `FK_Relationship_4` FOREIGN KEY (`User_ID`) REFERENCES `User` (`ID`)
      ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='键值对系统设置（AI 提示词、阶段文案等）';

/*==============================================================*/
/* Table: Candidate_File（候选人文件）                            */
/*==============================================================*/
CREATE TABLE `Candidate_File` (
  `ID`               INT NOT NULL AUTO_INCREMENT,
  `Candidate_ID`     INT NOT NULL COMMENT '所属候选人',
  `Application_ID`   INT DEFAULT NULL COMMENT '绑定某次投递时填写；个人文件为 NULL',
  `Category`         VARCHAR(20) NOT NULL COMMENT 'resume / certificate / portfolio / other / offer / offer_agreement / background_check',
  `Original_Name`    VARCHAR(255) NOT NULL COMMENT '原始文件名',
  `Mime_Type`        VARCHAR(100) NOT NULL COMMENT 'MIME 类型',
  `Size_Bytes`       INT NOT NULL COMMENT '字节数，单文件 ≤10MB',
  `Content`          LONGBLOB NOT NULL COMMENT '文件内容',
  `Is_Current`       TINYINT NOT NULL DEFAULT 1 COMMENT '1=当前版本；替换后旧版本置 0',
  `Uploaded_By_Role` VARCHAR(20) NOT NULL COMMENT 'candidate / hr',
  `Send_Time`        DATETIME DEFAULT NULL COMMENT '发送给候选人的时间；NULL=未发送（候选人不可见）',
  `Upload_Time`      DATETIME NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `IX_Cand_Cat_Current` (`Candidate_ID`, `Category`, `Is_Current`),
  KEY `IX_File_App` (`Application_ID`),
  CONSTRAINT `FK_File_Candidate` FOREIGN KEY (`Candidate_ID`) REFERENCES `Candidate` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `FK_File_Application` FOREIGN KEY (`Application_ID`) REFERENCES `Application` (`ID`)
      ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='候选人文件：HR 上传，候选人只读';


/*==============================================================*/
/* Table: Candidate_Notice（候选人通知：通过关卡时按模板发送）      */
/*==============================================================*/
CREATE TABLE `Candidate_Notice` (
  `ID`             INT NOT NULL AUTO_INCREMENT,
  `Candidate_ID`   INT NOT NULL COMMENT '所属候选人',
  `Application_ID` INT DEFAULT NULL COMMENT '关联投递；可能为空',
  `Stage`          VARCHAR(20) NOT NULL COMMENT '触发关卡：test / pro / hr / final',
  `Title`          VARCHAR(100) NOT NULL COMMENT '通知标题（按模板渲染）',
  `Body`           TEXT COMMENT '通知正文（按模板渲染）',
  `Send_Time`      DATETIME DEFAULT NULL COMMENT '发送时间；NULL=草稿（候选人不可见）',
  `Read_Time`      DATETIME DEFAULT NULL COMMENT '候选人阅读时间；NULL=未读（登录弹窗只看未读）',
  PRIMARY KEY (`ID`),
  KEY `IX_Notice_Cand` (`Candidate_ID`, `Read_Time`),
  KEY `IX_Notice_App` (`Application_ID`),
  CONSTRAINT `FK_Notice_Candidate` FOREIGN KEY (`Candidate_ID`) REFERENCES `Candidate` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `FK_Notice_Application` FOREIGN KEY (`Application_ID`) REFERENCES `Application` (`ID`)
      ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='候选人通知：HR 通过模板发送，候选人登录时弹窗展示';

/*==============================================================*/
/* Table: Form_Template（表单模板）                               */
/*==============================================================*/
CREATE TABLE `Form_Template` (
  `ID`          INT NOT NULL AUTO_INCREMENT,
  `Name`        VARCHAR(100) NOT NULL COMMENT '模板名',
  `Scope`       VARCHAR(20) NOT NULL COMMENT 'profile=个人资料表 / position=岗位申请表',
  `Position_ID` INT DEFAULT NULL COMMENT 'Scope=position 时必填',
  `Description` VARCHAR(500) DEFAULT NULL,
  `Version`     INT NOT NULL DEFAULT 1 COMMENT '字段变更时 +1',
  `Is_Active`   TINYINT NOT NULL DEFAULT 1 COMMENT '0=停用，候选人不再看到',
  `Created_By`  INT DEFAULT NULL COMMENT '创建人 User.ID',
  `Create_Time` DATETIME NOT NULL,
  `Update_Time` DATETIME NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `IX_Form_Scope` (`Scope`, `Position_ID`, `Is_Active`),
  CONSTRAINT `FK_Form_Position` FOREIGN KEY (`Position_ID`) REFERENCES `Position` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='可配置表单模板';

/*==============================================================*/
/* Table: Form_Field（表单字段）                                  */
/*==============================================================*/
CREATE TABLE `Form_Field` (
  `ID`           INT NOT NULL AUTO_INCREMENT,
  `Template_ID`  INT NOT NULL,
  `Field_Key`    VARCHAR(50) NOT NULL COMMENT '英文键，同一模板内唯一',
  `Label`        VARCHAR(100) NOT NULL COMMENT '显示名',
  `Field_Type`   VARCHAR(20) NOT NULL COMMENT 'text/textarea/number/date/select/radio/checkbox/email/phone',
  `Required`     TINYINT NOT NULL DEFAULT 0,
  `Options_JSON` TEXT DEFAULT NULL COMMENT 'select/radio/checkbox 的选项，JSON 数组',
  `Placeholder`  VARCHAR(200) DEFAULT NULL,
  `Help_Text`    VARCHAR(500) DEFAULT NULL,
  `Max_Length`   INT DEFAULT NULL,
  `Sort_Order`   INT NOT NULL DEFAULT 0,
  `Is_Active`    TINYINT NOT NULL DEFAULT 1 COMMENT '0=软删除，历史答案保留',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_Form_Field_Key` (`Template_ID`, `Field_Key`),
  CONSTRAINT `FK_Field_Template` FOREIGN KEY (`Template_ID`) REFERENCES `Form_Template` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='表单字段';

/*==============================================================*/
/* Table: Form_Submission（表单答卷）                             */
/*==============================================================*/
CREATE TABLE `Form_Submission` (
  `ID`               INT NOT NULL AUTO_INCREMENT,
  `Template_ID`      INT NOT NULL,
  `Candidate_ID`     INT NOT NULL,
  `Application_ID`   INT DEFAULT NULL COMMENT 'profile 表为 NULL；position 表填对应投递',
  `Template_Version` INT NOT NULL COMMENT '提交时的模板版本',
  `Status`           VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT 'draft / submitted',
  `Submit_Time`      DATETIME DEFAULT NULL,
  `Update_Time`      DATETIME NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `IX_Sub_Candidate` (`Candidate_ID`, `Template_ID`),
  KEY `IX_Sub_Application` (`Application_ID`),
  CONSTRAINT `FK_Sub_Template` FOREIGN KEY (`Template_ID`) REFERENCES `Form_Template` (`ID`)
      ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `FK_Sub_Candidate` FOREIGN KEY (`Candidate_ID`) REFERENCES `Candidate` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `FK_Sub_Application` FOREIGN KEY (`Application_ID`) REFERENCES `Application` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='候选人填写的表单答卷';

/*==============================================================*/
/* Table: Form_Answer（表单答案）                                 */
/*==============================================================*/
CREATE TABLE `Form_Answer` (
  `ID`            INT NOT NULL AUTO_INCREMENT,
  `Submission_ID` INT NOT NULL,
  `Field_ID`      INT NOT NULL,
  `Field_Key`     VARCHAR(50) NOT NULL COMMENT '快照，字段删除后仍可读',
  `Value_Text`    TEXT DEFAULT NULL COMMENT '统一存文本；多选存 JSON 数组',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_Answer_Field` (`Submission_ID`, `Field_ID`),
  CONSTRAINT `FK_Answer_Submission` FOREIGN KEY (`Submission_ID`) REFERENCES `Form_Submission` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `FK_Answer_Field` FOREIGN KEY (`Field_ID`) REFERENCES `Form_Field` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='表单答案，一个字段一行';

/*==============================================================*/
/* Table: Operation_Log（操作日志）                               */
/*==============================================================*/
CREATE TABLE `Operation_Log` (
  `ID`          BIGINT NOT NULL AUTO_INCREMENT,
  `User_ID`     INT DEFAULT NULL,
  `Username`    VARCHAR(50) DEFAULT NULL COMMENT '快照，账号删除后仍可读',
  `Role`        VARCHAR(20) DEFAULT NULL,
  `Action`      VARCHAR(50) NOT NULL COMMENT 'login/create/update/delete/reset_password/export/backup/config_change',
  `Target_Type` VARCHAR(30) DEFAULT NULL COMMENT 'candidate/application/file/form/user/ai_config/backup',
  `Target_ID`   INT DEFAULT NULL,
  `Detail_JSON` TEXT DEFAULT NULL,
  `IP`          VARCHAR(45) DEFAULT NULL,
  `Create_Time` DATETIME NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `IX_Log_Time` (`Create_Time`),
  KEY `IX_Log_User` (`User_ID`),
  KEY `IX_Log_Action` (`Action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='操作日志（技术管理端排查用）';
