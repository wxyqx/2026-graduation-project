-- v3.16：User 加 phone（HR / 技术管理员的个人信息强制要求有手机号）
-- 候选人的手机号仍在 Candidate 表（那是候选人端的登录账号），候选人账号此列保持 NULL。
-- 老库升级执行本脚本；新库直接跑 crebas.sql 即可。

ALTER TABLE `User`
  ADD COLUMN `phone` VARCHAR(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL
    COMMENT 'HR/技术管理员手机号（个人信息必填）；候选人账号为 NULL，手机号在 Candidate 表' AFTER `username`;

ALTER TABLE `User`
  ADD UNIQUE KEY `UK_User_Phone` (`phone`);

-- 给现有 HR / 技术管理员编一个手机号（13800000001 起顺延），满足「HR 必有手机号」；
-- 各人登录后可在「个人信息」里改成真实号码。
UPDATE `User`, (SELECT @p := 13800000000) AS init
SET `User`.`phone` = (@p := @p + 1)
WHERE `User`.`role` IN ('hr', 'admin')
  AND (`User`.`phone` IS NULL OR `User`.`phone` = '');
