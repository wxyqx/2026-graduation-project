/*==============================================================*/
/* v3.16 迁移：Candidate 表新增「HR 从简历摘录的个人信息」8 列     */
/*                                                              */
/* 与候选人填写的表单答卷无关：这是 HR 看简历时手工录入的档案字段， */
/* 两套数据各自独立，内容可能重叠但来源不同。                      */
/* 全部可空，不影响任何现有数据。                                  */
/*                                                              */
/* 执行一次即可（列已存在时会报 Duplicate column，属正常）：       */
/*   mysql -u root -p ats < migrate_v3.16_candidate_resume_fields.sql */
/* 新装机器直接跑 crebas.sql 即可，无需本脚本。                    */
/*==============================================================*/

ALTER TABLE Candidate
  ADD COLUMN onboard_date    VARCHAR(50)  COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '到岗时间（HR 从简历摘录，可写「随时」等）',
  ADD COLUMN school          VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '毕业院校',
  ADD COLUMN degree          VARCHAR(20)  COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '学历（大专/本科/硕士/博士/其他）',
  ADD COLUMN major           VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '专业',
  ADD COLUMN expected_salary VARCHAR(50)  COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '期望薪资',
  ADD COLUMN work_location   VARCHAR(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '期望工作地点',
  ADD COLUMN hire_type       VARCHAR(20)  COLLATE utf8mb4_unicode_ci DEFAULT NULL COMMENT '招聘类型（校招/社招）',
  ADD COLUMN work_experience TEXT         COLLATE utf8mb4_unicode_ci COMMENT '工作经历（HR 从简历摘录）';
