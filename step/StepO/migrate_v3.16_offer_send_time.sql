/*==============================================================*/
/* v3.16 迁移：Candidate_File 表新增 Send_Time（Offer 文件发送时间）*/
/*                                                              */
/* Offer 文件（录用协议 / offer / 背景调查）上传后先不发给候选人，  */
/* HR 预览确认后点「发送」，Send_Time 记录发送时间；               */
/* Send_Time 为空 = 未发送，候选人端不可见。                      */
/*                                                              */
/* 执行一次即可（列已存在时报 Duplicate column，属正常）：         */
/*   mysql -u root -p ats < migrate_v3.16_offer_send_time.sql    */
/* 新装机器直接跑 crebas.sql 即可，无需本脚本。                    */
/*==============================================================*/

ALTER TABLE Candidate_File
  ADD COLUMN Send_Time DATETIME DEFAULT NULL COMMENT '发送给候选人的时间；NULL=未发送（候选人不可见）';
