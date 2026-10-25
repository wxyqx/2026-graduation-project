/*==============================================================*/
/* v3.16 迁移：Candidate_Notice.Send_Time 改为可空                */
/*                                                              */
/* 通知改为「草稿 → 编辑 → 发送」：通过关卡时按模板生成草稿        */
/* （Send_Time 为空，候选人不可见），HR 在投递详情逐人编辑后发送，   */
/* 发送时写入 Send_Time。                                        */
/*                                                              */
/* 执行一次即可：                                                 */
/*   mysql -u root -p ats < migrate_v3.16_notice_draft.sql       */
/*==============================================================*/

ALTER TABLE Candidate_Notice
  MODIFY COLUMN Send_Time DATETIME DEFAULT NULL COMMENT '发送时间；NULL=草稿（候选人不可见）';
