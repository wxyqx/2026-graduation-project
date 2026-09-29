/*==============================================================*/
/* DBMS name:      MySQL 5.0                                    */
/* Created on:     2026/9/8 16:03:58                            */
/*==============================================================*/


drop table if exists AI_API_Config;

drop table if exists App_Setting;

drop index UK_Can_Pos on Application;

drop table if exists Application;

drop table if exists Candidate;

drop table if exists Position;

drop table if exists User;

/*==============================================================*/
/* Table: App_Setting                                           */
/*==============================================================*/
create table App_Setting
(
   ID                   INT not null auto_increment,
   User_ID              INT not null,
   setting_key          VARCHAR(50) not null,
   setting_value        TEXT,
   update_time          DATETIME,
   primary key (ID),
   key UK_User_Key (User_ID, setting_key)
);

/*==============================================================*/
/* Table: AI_API_Config                                         */
/*==============================================================*/
create table AI_API_Config
(
   ID                   INT not null auto_increment,
   name                 VARCHAR(50) not null,
   base_url             VARCHAR(255) not null,
   api_key              VARCHAR(255) not null,
   model                VARCHAR(100) not null,
   is_enabled           TINYINT default 0,
   User_ID              INT not null,
   primary key (ID)
);

/*==============================================================*/
/* Table: Application                                           */
/*==============================================================*/
create table Application
(
   ID                   int not null auto_increment,
   Can_ID               INT not null,
   Pos_ID               INT not null,
   ai_result            VARCHAR(20),
   resume_submit_time   DATETIME,
   resume_result        VARCHAR(20),
   phone_time           DATETIME,
   phone_result         VARCHAR(20),
   test_time            DATETIME,
   test_result          VARCHAR(20),
   pro_result           VARCHAR(20),
   hr_result            VARCHAR(20),
   final_result         VARCHAR(20),
   final_time           DATETIME,
   current_stage        VARCHAR(20),
   create_time          DATETIME,
   update_time          DATETIME,
   hr_time              DATETIME,
   pro_time             DATETIME,
   overall_status       VARCHAR(20)  not null default 'pending',
   ai_comment           VARCHAR(500),
   resume_reason        TEXT,
   phone_reason         TEXT,
   phone_evaluation     TEXT,
   test_reason          TEXT,
   pro_reason           TEXT,
   pro_evaluation       TEXT,
   hr_reason            TEXT,
   hr_evaluation        TEXT,
   final_reason         TEXT,
   final_evaluation     TEXT,
   primary key (ID)
);

/*==============================================================*/
/* Index: UK_Can_Pos                                            */
/*==============================================================*/
create unique index UK_Can_Pos on Application
(
   Can_ID,
   Pos_ID
);

/*==============================================================*/
/* Table: Candidate                                             */
/*==============================================================*/
create table Candidate
(
   ID                   INT not null auto_increment,
   create_time          DATETIME,
   name                 VARCHAR(255),
   remark               VARCHAR(500),
   primary key (ID)
);

/*==============================================================*/
/* Table: Position                                              */
/*==============================================================*/
create table Position
(
   ID                   INT not null auto_increment,
   position_name        VARCHAR(100),
   owner                VARCHAR(100),
   position_requirements VARCHAR(2000),
   is_hidden            TINYINT default 0,
   primary key (ID)
);

/*==============================================================*/
/* Table: User                                                  */
/*==============================================================*/
create table User
(
   ID                   INT not null auto_increment,
   username             VARCHAR(50) not null,
   password_hash        VARCHAR(100) not null,
   create_time          DATETIME,
   primary key (ID),
   key AK_Username_UK (username)
);

alter table AI_API_Config add constraint FK_Relationship_3 foreign key (User_ID)
      references User (ID) on delete restrict on update restrict;

alter table App_Setting add constraint FK_Relationship_4 foreign key (User_ID)
      references User (ID) on delete restrict on update restrict;

alter table Application add constraint FK_Relationship_1 foreign key (Pos_ID)
      references Position (ID) on delete restrict on update restrict;

alter table Application add constraint FK_Relationship_2 foreign key (Can_ID)
      references Candidate (ID) on delete restrict on update restrict;

