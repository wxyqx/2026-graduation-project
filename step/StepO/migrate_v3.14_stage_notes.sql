/*==============================================================*/
/* v3.14 迁移：Application 表新增「各关原因 / 面试评价」10 个可空列   */
/*                                                              */
/* 只新增 TEXT NULL 列，不修改、不删除任何现有数据。               */
/* 各阶段新增：                                                  */
/*   简历筛选          resume_reason                             */
/*   电话沟通          phone_reason  + phone_evaluation           */
/*   笔试              test_reason                               */
/*   专业面            pro_reason    + pro_evaluation             */
/*   HR面             hr_reason     + hr_evaluation              */
/*   终面              final_reason  + final_evaluation           */
/* AI筛选（ai）不在此列：其理由沿用已有的 ai_comment，由 AI 生成。 */
/*                                                              */
/* 执行一次即可（列已存在时会报 Duplicate column，属正常）：       */
/*   mysql -u root -p ats < migrate_v3.14_stage_notes.sql        */
/* 新装机器直接跑 crebas.sql 即可，无需本脚本。                    */
/*==============================================================*/

ALTER TABLE Application
  ADD COLUMN resume_reason    TEXT NULL COMMENT '简历筛选结果原因（通过/淘汰）',
  ADD COLUMN phone_reason     TEXT NULL COMMENT '电话沟通结果原因（通过/淘汰）',
  ADD COLUMN phone_evaluation TEXT NULL COMMENT '电话沟通面试评价',
  ADD COLUMN test_reason      TEXT NULL COMMENT '笔试结果原因（通过/淘汰）',
  ADD COLUMN pro_reason       TEXT NULL COMMENT '专业面结果原因（通过/淘汰）',
  ADD COLUMN pro_evaluation   TEXT NULL COMMENT '专业面面试评价',
  ADD COLUMN hr_reason        TEXT NULL COMMENT 'HR面结果原因（通过/淘汰）',
  ADD COLUMN hr_evaluation    TEXT NULL COMMENT 'HR面面试评价',
  ADD COLUMN final_reason     TEXT NULL COMMENT '终面结果原因（通过/淘汰）',
  ADD COLUMN final_evaluation TEXT NULL COMMENT '终面面试评价';
