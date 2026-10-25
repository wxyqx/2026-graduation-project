-- v3.16：User 加 restore_time（淘汰销号账号的恢复时间）
-- 淘汰销号只是停用（is_active=0），候选人资料/投递/通知全部保留；
-- 技术管理员在保存期（淘汰销号后 3 个月/90 天）内启用账号即恢复，写入本时间戳；
-- 恢复时间晚于某次淘汰时间的，那次淘汰不再拦截登录。老库升级执行本脚本。

ALTER TABLE `User`
  ADD COLUMN `restore_time` DATETIME DEFAULT NULL
    COMMENT '淘汰销号账号的恢复时间；恢复后该次淘汰不再拦截登录' AFTER `is_active`;
