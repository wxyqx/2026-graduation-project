/*==============================================================*/
/* v3.16 迁移：新增 Candidate_Notice 表（候选人通过关卡通知）      */
/*                                                              */
/* 笔试/专业面/HR面/终面通过时，若 HR 开启了该关的通过通知，        */
/* 按模板渲染后写入本表；候选人登录时弹窗展示未读通知。            */
/*                                                              */
/* 执行一次即可（表已存在时报 Table exists，属正常）：             */
/*   mysql -u root -p ats < migrate_v3.16_candidate_notice.sql   */
/* 新装机器直接跑 crebas.sql 即可，无需本脚本。                    */
/*==============================================================*/

CREATE TABLE `Candidate_Notice` (
  `ID`             INT NOT NULL AUTO_INCREMENT,
  `Candidate_ID`   INT NOT NULL COMMENT '所属候选人',
  `Application_ID` INT DEFAULT NULL COMMENT '关联投递；可能为空',
  `Stage`          VARCHAR(20) NOT NULL COMMENT '触发关卡：test / pro / hr / final',
  `Title`          VARCHAR(100) NOT NULL COMMENT '通知标题（按模板渲染）',
  `Body`           TEXT COMMENT '通知正文（按模板渲染）',
  `Send_Time`      DATETIME NOT NULL COMMENT '发送时间',
  `Read_Time`      DATETIME DEFAULT NULL COMMENT '候选人阅读时间；NULL=未读（登录弹窗只看未读）',
  PRIMARY KEY (`ID`),
  KEY `IX_Notice_Cand` (`Candidate_ID`, `Read_Time`),
  KEY `IX_Notice_App` (`Application_ID`),
  CONSTRAINT `FK_Notice_Candidate` FOREIGN KEY (`Candidate_ID`) REFERENCES `Candidate` (`ID`)
      ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `FK_Notice_Application` FOREIGN KEY (`Application_ID`) REFERENCES `Application` (`ID`)
      ON DELETE SET NULL ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='候选人通知：HR 通过模板发送，候选人登录时弹窗展示';
