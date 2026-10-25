/*==============================================================*/
/* v3.16 迁移：User 表新增头像两列（三个端都能上传头像）            */
/*                                                              */
/* 头像直接存库（LONGBLOB），与文件同思路；NULL=未设置，前端显示    */
/* 用户名首字作为占位。图片仅限 image/*，≤5MB，接口侧校验。        */
/*                                                              */
/* 执行一次即可（列已存在时报 Duplicate column，属正常）：         */
/*   mysql -u root -p ats < migrate_v3.16_user_avatar.sql        */
/* 新装机器直接跑 crebas.sql 即可，无需本脚本。                    */
/*==============================================================*/

ALTER TABLE `User`
  ADD COLUMN `Avatar` LONGBLOB COMMENT '头像图片内容；NULL=未设置',
  ADD COLUMN `Avatar_Mime` VARCHAR(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '头像 MIME 类型';
