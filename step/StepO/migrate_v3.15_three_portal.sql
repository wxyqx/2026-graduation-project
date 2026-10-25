/*==============================================================*/
/* v3.15 迁移：三角色 + 候选人手机号 + 文件 + 可配置表单 + 日志   */
/*                                                              */
/* 适用：从 v3.14（6 张表）升级到 v3.15（12 张表）。               */
/* 原则：只加列 / 加索引 / 加表，不删除、不改动任何现有数据。      */
/*                                                              */
/* 执行前务必：                                                  */
/*   1. 备份数据库（mysqldump）                                  */
/*   2. 确认 MySQL max_allowed_packet >= 16M（默认 64M 即可）     */
/*   3. 在副本库先演练一遍                                       */
/*                                                              */
/* 执行：                                                        */
/*   mysql -u root -p --default-character-set=utf8mb4 ats \      */
/*         < migrate_v3.15_three_portal.sql                      */
/*                                                              */
/* 注意：MySQL 的 DDL 会自动提交，不能回滚；出错请用备份恢复。    */
/*==============================================================*/

SET NAMES utf8mb4;

/*--------------------------------------------------------------*/
/* 1. User：三角色账号                                          */
/*--------------------------------------------------------------*/
ALTER TABLE `User`
  MODIFY COLUMN `username` VARCHAR(50) COLLATE utf8mb4_unicode_ci NULL
      COMMENT 'HR/技术管理员用户名；候选人账号为 NULL',
  ADD COLUMN `role` VARCHAR(20) NOT NULL DEFAULT 'hr'
      COMMENT 'candidate=候选人 / hr=HR / admin=技术管理员',
  ADD COLUMN `candidate_id` INT NULL
      COMMENT '候选人账号关联的 Candidate.ID；HR 与管理员为 NULL',
  ADD COLUMN `is_active` TINYINT NOT NULL DEFAULT 1
      COMMENT '0=停用，禁止登录',
  ADD COLUMN `last_login_time` DATETIME NULL COMMENT '最近登录时间',
  ADD COLUMN `last_login_ip` VARCHAR(45) NULL COMMENT '最近登录 IP',
  DROP INDEX `AK_Username_UK`,
  ADD UNIQUE KEY `AK_Username_UK` (`username`),
  ADD UNIQUE KEY `UK_User_Candidate` (`candidate_id`),
  ADD CONSTRAINT `FK_User_Candidate` FOREIGN KEY (`candidate_id`)
      REFERENCES `Candidate` (`ID`) ON DELETE SET NULL ON UPDATE RESTRICT;

/* 存量账号全部按 HR 处理（默认值已生效，这里显式写一遍便于核对） */
UPDATE `User` SET `role` = 'hr' WHERE `role` IS NULL OR `role` = '';

/*--------------------------------------------------------------*/
/* 2. Candidate：手机号即账号                                   */
/*--------------------------------------------------------------*/
ALTER TABLE `Candidate`
  ADD COLUMN `phone` VARCHAR(20) NULL
      COMMENT '手机号：候选人端登录账号，唯一',
  ADD COLUMN `email` VARCHAR(100) NULL COMMENT '邮箱（可空，不做验证）',
  ADD COLUMN `update_time` DATETIME NULL COMMENT '最近更新时间',
  ADD UNIQUE KEY `UK_Candidate_Phone` (`phone`);

/*--------------------------------------------------------------*/
/* 3. Application：来源标记                                     */
/*--------------------------------------------------------------*/
ALTER TABLE `Application`
  ADD COLUMN `source` VARCHAR(20) NOT NULL DEFAULT 'admin'
      COMMENT 'admin=HR手动 / ai_intake=AI录入 / portal=候选人自主投递';

/* 存量投递全部视为 HR 手动/AI 录入，统一先标 admin，后续按需人工订正 */
UPDATE `Application` SET `source` = 'admin' WHERE `source` IS NULL OR `source` = '';

/*--------------------------------------------------------------*/
/* 4. Candidate_File：候选人文件（BLOB 入库）                     */
/*--------------------------------------------------------------*/
CREATE TABLE `Candidate_File` (
  `ID`               INT NOT NULL AUTO_INCREMENT,
  `Candidate_ID`     INT NOT NULL COMMENT '所属候选人',
  `Application_ID`   INT NULL COMMENT '绑定某次投递时填写；个人文件为 NULL',
  `Category`         VARCHAR(20) NOT NULL COMMENT 'resume / certificate / portfolio / other',
  `Original_Name`    VARCHAR(255) NOT NULL COMMENT '原始文件名',
  `Mime_Type`        VARCHAR(100) NOT NULL COMMENT 'MIME 类型',
  `Size_Bytes`       INT NOT NULL COMMENT '字节数，单文件 ≤10MB',
  `Content`          LONGBLOB NOT NULL COMMENT '文件内容',
  `Is_Current`       TINYINT NOT NULL DEFAULT 1 COMMENT '1=当前版本；替换后旧版本置 0',
  `Uploaded_By_Role` VARCHAR(20) NOT NULL COMMENT 'candidate / hr',
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

/*--------------------------------------------------------------*/
/* 5. Form_Template：表单模板                                   */
/*--------------------------------------------------------------*/
CREATE TABLE `Form_Template` (
  `ID`          INT NOT NULL AUTO_INCREMENT,
  `Name`        VARCHAR(100) NOT NULL COMMENT '模板名',
  `Scope`       VARCHAR(20) NOT NULL COMMENT 'profile=个人资料表 / position=岗位申请表',
  `Position_ID` INT NULL COMMENT 'Scope=position 时必填',
  `Description` VARCHAR(500) NULL,
  `Version`     INT NOT NULL DEFAULT 1 COMMENT '字段变更时 +1',
  `Is_Active`   TINYINT NOT NULL DEFAULT 1 COMMENT '0=停用，候选人不再看到',
  `Created_By`  INT NULL COMMENT '创建人 User.ID',
  `Create_Time` DATETIME NOT NULL,
  `Update_Time` DATETIME NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `IX_Form_Scope` (`Scope`, `Position_ID`, `Is_Active`),
  CONSTRAINT `FK_Form_Position` FOREIGN KEY (`Position_ID`) REFERENCES `Position` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='可配置表单模板';

/*--------------------------------------------------------------*/
/* 6. Form_Field：表单字段                                      */
/*--------------------------------------------------------------*/
CREATE TABLE `Form_Field` (
  `ID`           INT NOT NULL AUTO_INCREMENT,
  `Template_ID`  INT NOT NULL,
  `Field_Key`    VARCHAR(50) NOT NULL COMMENT '英文键，同一模板内唯一',
  `Label`        VARCHAR(100) NOT NULL COMMENT '显示名',
  `Field_Type`   VARCHAR(20) NOT NULL COMMENT 'text/textarea/number/date/select/radio/checkbox/email/phone',
  `Required`     TINYINT NOT NULL DEFAULT 0,
  `Options_JSON` TEXT NULL COMMENT 'select/radio/checkbox 的选项，JSON 数组',
  `Placeholder`  VARCHAR(200) NULL,
  `Help_Text`    VARCHAR(500) NULL,
  `Max_Length`   INT NULL,
  `Sort_Order`   INT NOT NULL DEFAULT 0,
  `Is_Active`    TINYINT NOT NULL DEFAULT 1 COMMENT '0=软删除，历史答案保留',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_Form_Field_Key` (`Template_ID`, `Field_Key`),
  CONSTRAINT `FK_Field_Template` FOREIGN KEY (`Template_ID`) REFERENCES `Form_Template` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='表单字段';

/*--------------------------------------------------------------*/
/* 7. Form_Submission：表单答卷                                 */
/*--------------------------------------------------------------*/
CREATE TABLE `Form_Submission` (
  `ID`               INT NOT NULL AUTO_INCREMENT,
  `Template_ID`      INT NOT NULL,
  `Candidate_ID`     INT NOT NULL,
  `Application_ID`   INT NULL COMMENT 'profile 表为 NULL；position 表填对应投递',
  `Template_Version` INT NOT NULL COMMENT '提交时的模板版本',
  `Status`           VARCHAR(20) NOT NULL DEFAULT 'draft' COMMENT 'draft / submitted',
  `Submit_Time`      DATETIME NULL,
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

/*--------------------------------------------------------------*/
/* 8. Form_Answer：表单答案                                     */
/*--------------------------------------------------------------*/
CREATE TABLE `Form_Answer` (
  `ID`            INT NOT NULL AUTO_INCREMENT,
  `Submission_ID` INT NOT NULL,
  `Field_ID`      INT NOT NULL,
  `Field_Key`     VARCHAR(50) NOT NULL COMMENT '快照，字段删除后仍可读',
  `Value_Text`    TEXT NULL COMMENT '统一存文本；多选存 JSON 数组',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_Answer_Field` (`Submission_ID`, `Field_ID`),
  CONSTRAINT `FK_Answer_Submission` FOREIGN KEY (`Submission_ID`) REFERENCES `Form_Submission` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `FK_Answer_Field` FOREIGN KEY (`Field_ID`) REFERENCES `Form_Field` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='表单答案，一个字段一行';

/*--------------------------------------------------------------*/
/* 9. Operation_Log：操作日志                                   */
/*--------------------------------------------------------------*/
CREATE TABLE `Operation_Log` (
  `ID`          BIGINT NOT NULL AUTO_INCREMENT,
  `User_ID`     INT NULL,
  `Username`    VARCHAR(50) NULL COMMENT '快照，账号删除后仍可读',
  `Role`        VARCHAR(20) NULL,
  `Action`      VARCHAR(50) NOT NULL COMMENT 'login/create/update/delete/reset_password/export/backup/config_change',
  `Target_Type` VARCHAR(30) NULL COMMENT 'candidate/application/file/form/user/ai_config/backup',
  `Target_ID`   INT NULL,
  `Detail_JSON` TEXT NULL,
  `IP`          VARCHAR(45) NULL,
  `Create_Time` DATETIME NOT NULL,
  PRIMARY KEY (`ID`),
  KEY `IX_Log_Time` (`Create_Time`),
  KEY `IX_Log_User` (`User_ID`),
  KEY `IX_Log_Action` (`Action`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='操作日志（技术管理端排查用）';

/*--------------------------------------------------------------*/
/* 10. 校验：迁移后应看到 12 张表                                */
/*--------------------------------------------------------------*/
SELECT TABLE_NAME, TABLE_ROWS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME;
