/*==============================================================*/
/* v3.15 回滚：把三角色 / 文件 / 表单 / 日志全部退回 v3.14        */
/*                                                              */
/* 警告：回滚会丢弃以下数据（不可恢复）：                         */
/*   · Candidate.phone / email / update_time                     */
/*   · Application.source                                       */
/*   · 6 张新表里的全部内容（文件、表单、日志）                   */
/*                                                              */
/* 回滚前请先确认：                                             */
/*   1. 没有 role <> 'hr' 的账号（候选人和技术管理员要先停用/删除）*/
/*   2. User.username 全部非 NULL                               */
/*   3. 已另有备份                                               */
/*                                                              */
/* 执行：                                                        */
/*   mysql -u root -p ats < rollback_v3.15_three_portal.sql      */
/*==============================================================*/

SET NAMES utf8mb4;

/* 1. 先删有外键依赖的新表（子表在前，父表在后） */
DROP TABLE IF EXISTS `Form_Answer`;
DROP TABLE IF EXISTS `Form_Submission`;
DROP TABLE IF EXISTS `Form_Field`;
DROP TABLE IF EXISTS `Form_Template`;
DROP TABLE IF EXISTS `Candidate_File`;
DROP TABLE IF EXISTS `Operation_Log`;

/* 2. Application 去掉来源 */
ALTER TABLE `Application`
  DROP COLUMN `source`;

/* 3. User 去掉角色与候选人绑定 */
ALTER TABLE `User`
  DROP FOREIGN KEY `FK_User_Candidate`,
  DROP INDEX `UK_User_Candidate`,
  DROP INDEX `AK_Username_UK`,
  ADD KEY `AK_Username_UK` (`username`),
  DROP COLUMN `last_login_ip`,
  DROP COLUMN `last_login_time`,
  DROP COLUMN `is_active`,
  DROP COLUMN `candidate_id`,
  DROP COLUMN `role`;

/* 注意：若存在 username 为 NULL 的候选人账号，下面这句会失败。
   先处理干净再执行：DELETE FROM `User` WHERE `role` <> 'hr'（仅回滚演练库可这样做）。 */
ALTER TABLE `User`
  MODIFY COLUMN `username` VARCHAR(50) NOT NULL;

/* 4. Candidate 去掉手机号等 */
ALTER TABLE `Candidate`
  DROP INDEX `UK_Candidate_Phone`,
  DROP COLUMN `update_time`,
  DROP COLUMN `email`,
  DROP COLUMN `phone`;

/* 5. 校验：应只剩 v3.14 的 6 张表 */
SELECT TABLE_NAME, TABLE_ROWS
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = DATABASE()
ORDER BY TABLE_NAME;
