-- v3.16：候选人负责人 + 投递阶段负责人
-- Candidate.owner_id：候选人负责人 HR（默认 = 建档/上传简历录入的 HR），可编辑该候选人全部关卡；
--   技术管理端可单个或批量改。老数据为 NULL = 暂无负责人（任意 HR 可编辑）。
-- Stage_Owner：每关的负责人（第一次编辑该关的 HR 自动认领），只能编辑本关，其他关只读。

ALTER TABLE `Candidate`
  ADD COLUMN `owner_id` INT DEFAULT NULL COMMENT '候选人负责人 HR（User.ID）；NULL=暂无，任意 HR 可编辑' AFTER `remark`;

ALTER TABLE `Candidate`
  ADD CONSTRAINT `FK_Candidate_Owner` FOREIGN KEY (`owner_id`) REFERENCES `User` (`ID`)
      ON DELETE SET NULL ON UPDATE RESTRICT;

CREATE TABLE `Stage_Owner` (
  `ID`             INT NOT NULL AUTO_INCREMENT,
  `application_id` INT NOT NULL COMMENT '投递编号',
  `stage`          VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '关卡：ai/resume/phone/test/pro/hr/final',
  `user_id`        INT DEFAULT NULL COMMENT '该关负责人 HR（User.ID）',
  `update_time`    DATETIME DEFAULT NULL COMMENT '认领/变更时间',
  PRIMARY KEY (`ID`),
  UNIQUE KEY `UK_App_Stage` (`application_id`, `stage`),
  KEY `FK_Stage_Owner_User` (`user_id`),
  CONSTRAINT `FK_Stage_Owner_App` FOREIGN KEY (`application_id`) REFERENCES `Application` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `FK_Stage_Owner_User` FOREIGN KEY (`user_id`) REFERENCES `User` (`ID`)
      ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='投递的阶段负责人';
