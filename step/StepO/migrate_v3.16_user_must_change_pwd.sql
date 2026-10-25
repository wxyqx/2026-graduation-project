-- v3.16：User 加 must_change_password（默认密码强提示）
-- 1 = 账号还在用默认密码：候选人每次登录弹「请修改密码」强提示，改密成功清零。
-- 建号（ensure_candidate_account）、技术端重置密码时置 1。

ALTER TABLE `User`
  ADD COLUMN `must_change_password` TINYINT NOT NULL DEFAULT 0
    COMMENT '1=还在用默认密码，登录强提示改密；改密成功清零' AFTER `is_active`;

-- 存量候选人账号全部回填：默认密码开局，从未改过的一律提示
-- （极少数已改过密码的会多提示一次，改完即消失，代价可接受）
UPDATE `User` SET `must_change_password` = 1 WHERE `role` = 'candidate';
