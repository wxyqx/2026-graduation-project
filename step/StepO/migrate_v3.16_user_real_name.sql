-- v3.16：User 加 real_name（HR / 技术管理员实名，必填）
-- 候选人的姓名仍在 Candidate 表，候选人账号此列保持 NULL。
-- 老库升级执行本脚本；新库直接跑 crebas.sql 即可。

ALTER TABLE `User`
  ADD COLUMN `real_name` VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL
    COMMENT 'HR/技术管理员实名（必填）；候选人账号为 NULL，姓名在 Candidate 表' AFTER `phone`;

-- 给现有 HR / 技术管理员编一个名字（占位，登录后可在「个人信息」里改成真实姓名）
UPDATE `User` SET `real_name` = '张伟明' WHERE `role` IN ('hr', 'admin') AND `username` = 'm3test';
UPDATE `User` SET `real_name` = '李雨桐' WHERE `role` IN ('hr', 'admin') AND `username` = 'AineOnly';
UPDATE `User` SET `real_name` = '王建国' WHERE `role` IN ('hr', 'admin') AND `username` = 'tech';
-- 兜底：还有漏网的 HR / 管理员统一编「待补实名+编号」
UPDATE `User`, (SELECT @n := 0) AS init
SET `User`.`real_name` = CONCAT('待补实名', (@n := @n + 1))
WHERE `User`.`role` IN ('hr', 'admin') AND (`User`.`real_name` IS NULL OR `User`.`real_name` = '');
