# 在线教育业务数据
## 业务概述
在线教育平台面向机构、教师、学员和平台运营团队提供统一的教学与经营支撑能力，覆盖课程供给、招生转化、交易支付、学习过程、互动服务和经营分析等完整业务链路。

平台覆盖的核心业务对象：

- 机构、校区、部门、教室、直播间等组织与教学资源
- 平台账号、职员档案、教师档案、学员档案等用户主体
- 课程系列、课程模块、班次、课次、作业、考试、题库等教学内容
- 购物车、咨询、领券、订单、支付、退款、报名关系等转化与交易对象
- 考勤、视频播放、作业提交、考试提交、讨论、评价、工单等学习与服务记录
- 教师课酬、渠道返佣、风险预警、内容审核等经营衍生结果

平台核心业务能力：

- 组织与资源管理：维护机构、校区、部门、教室和直播间等资源主档。
- 用户与档案管理：维护平台账号、职员信息、教师信息和学员画像。
- 课程与教务管理：维护课程系列、班次、课次、授课安排、教学资源和测评对象。
- 招生与营销管理：支撑流量渠道、咨询、领券、购物车和课程转化准备过程。
- 交易与履约管理：完成订单创建、支付、退款和报名关系建立。
- 学习与互动管理：记录考勤、视频、作业、考试、讨论和评价过程。
- 经营与风控管理：沉淀课酬、返佣、风控和审核结果。

平台主链路：

- 浏览课程
- 搜索课程
- 咨询或领券
- 加购与下单
- 支付报名
- 进入班次学习
- 提交作业与考试
- 互动评价
- 售后退费

## 快速开始
启动 MySQL 数据库

配置数据库连接参数 [`.env`](./.env)

```bash
uv sync  # 安装依赖

uv run init_db.py  # 初始化数据库
uv run -m generate.main --profile full  # 生成数据

uv run -m app.main  # 启动服务
```

服务启动后访问 FastAPI 文档：

- Swagger UI：`http://127.0.0.1:8000/docs`
- OpenAPI JSON：`http://127.0.0.1:8000/openapi.json`

## 数据定义
### 基础维度
本域用于维护全平台共享的基础主数据。

表说明：

- `dim_channel`：维护机构招生渠道，用于咨询、订单、返佣等获客与转化归因场景。
- `dim_course_category`：维护课程分类体系，支持父子层级关系。
- `dim_question_type`：维护题型。
- `dim_learning_goal`：维护学习目标。
- `dim_education_level`：维护学历层次。
- `dim_learner_identity`：维护学习者身份。
- `dim_grade`：维护学段和年级体系，支持父子层级关系。

依赖关系说明：

- `dim_course_category` 通过 `parent_id` 自关联，形成课程分类树。
- `dim_grade` 通过 `parent_id` 自关联，形成学段与年级层级。

#### `dim_channel`
机构招生渠道维表，定义机构获客、咨询、转化过程中使用的招生渠道。

- `acquisition`：获客渠道
  - `organic`：自然流量
  - `app_store`：应用商店
  - `seo`：搜索引擎优化
  - `content_platform`：内容平台
  - `advertising`：广告投放
  - `short_video_ads`：短视频投放
  - `search_ads`：搜索广告
  - `information_flow_ads`：信息流广告
- `referral`：转介绍渠道
  - `social_referral`：社交裂变
  - `friend_referral`：老带新
  - `teacher_referral`：教师转介绍
  - `private_domain`：私域运营
- `offline`：线下活动渠道
  - `offline_activity`：线下活动
  - `campus_promotion`：校区地推
  - `public_lecture`：公开讲座
  - `education_expo`：教育展会
- `cooperation`：合作渠道
  - `b2b_cooperation`：机构合作
  - `school_cooperation`：学校合作
  - `enterprise_cooperation`：企业合作
  - `partner_channel`：渠道代理

- `id`：主键 ID。
- `channel_category_code`：渠道类别编码。
- `channel_category_name`：渠道类别名称。
- `channel_code`：渠道编码。
- `channel_name`：渠道名称。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_channel_code (channel_category_code, channel_code)`
- 外键约束：
  - 无
- 业务约束：
  - 无

#### `dim_course_category`
课程分类维表，定义学科、方向、课程层级等分类体系。

- `id`：主键 ID。
- `parent_id`：父分类 ID，关联 `dim_course_category.id`，顶级分类为空，子分类指向上一级分类。
- `category_code`：分类编码，作为课程分类业务唯一标识。
- `category_name`：分类名称，例如“考研”“雅思”“Python 开发”“高一数学”。
- `category_level`：分类层级，用于区分一级分类、二级分类、三级分类等层级结构。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_course_category_code (category_code)`
- 外键约束：
  - `fk_dim_course_category_parent (parent_id -> dim_course_category.id)`
- 业务约束：
  - 顶级分类 `parent_id` 为空，非顶级分类 `parent_id` 不为空
  - 子分类的 `category_level` 必须大于父分类的 `category_level`

#### `dim_question_type`
题型维表，定义单选、多选、判断、简答等题目类型。

- `single_choice`：单选题
- `multiple_choice`：多选题
- `true_false`：判断题
- `fill_blank`：填空题
- `short_answer`：简答题
- `essay`：论述题
- `calculation`：计算题
- `composition`：作文题
- `reading_comprehension`：阅读理解题
- `material_analysis`：材料分析题
- `case_study`：案例分析题
- `oral_test`：口语题
- `coding`：编程题
- `matching`：连线题
- `ordering`：排序题
- `cloze`：完形填空题
- `translation`：翻译题
- `listening`：听力题
- `practical_operation`：实操题
- `project`：项目题
- `drawing`：作图题
- `proof`：证明题
- `experiment`：实验题
- `scenario_analysis`：情境分析题
- `audio_video_analysis`：音视频分析题
- `formula_derivation`：公式推导题
- `document_revision`：文稿修改题
- `data_analysis`：数据分析题

- `id`：主键 ID。
- `type_code`：题型编码。
- `type_name`：题型名称。
- `objective_flag`：是否客观题，`1` 表示客观题，`0` 表示主观题。
- `auto_marking_flag`：是否支持自动判分，`1` 表示支持自动判分，`0` 表示必须人工批改。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_question_type_code (type_code)`
- 外键约束：
  - 无
- 业务约束：
  - 无

#### `dim_learner_identity`
学习者身份维表，定义在校生、职场人、转岗人群等用户身份。

- `in_school_student`：在校生
- `working_professional`：职场人
- `job_seeker`：求职者
- `freelancer`：自由职业者

- `id`：主键 ID。
- `identity_code`：学习者身份编码。
- `identity_name`：学习者身份名称。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_learner_identity_code (identity_code)`
- 外键约束：
  - 无
- 业务约束：
  - 无

#### `dim_grade`
学业层级维表，定义学段、年级等层级体系。

- `primary`：小学
  - `primary_1`：小学一年级
  - `primary_2`：小学二年级
  - `primary_3`：小学三年级
  - `primary_4`：小学四年级
  - `primary_5`：小学五年级
  - `primary_6`：小学六年级
- `junior_middle`：初中
  - `junior_1`：初中一年级
  - `junior_2`：初中二年级
  - `junior_3`：初中三年级
- `senior_high`：高中
  - `senior_1`：高中一年级
  - `senior_2`：高中二年级
  - `senior_3`：高中三年级
- `junior_college`：专科
  - `college_1`：专科一年级
  - `college_2`：专科二年级
  - `college_3`：专科三年级
- `undergraduate`：本科
  - `undergraduate_1`：本科一年级
  - `undergraduate_2`：本科二年级
  - `undergraduate_3`：本科三年级
  - `undergraduate_4`：本科四年级
- `master`：硕士研究生
- `doctor`：博士研究生

- `id`：主键 ID。
- `parent_id`：父层级 ID，关联 `dim_grade.id`，顶级学段为空，具体年级指向所属学段。
- `grade_code`：层级编码，作为学段或年级的业务唯一标识。
- `grade_name`：层级名称。
- `grade_type`：层级类型，枚举值包括 `stage`、`grade`。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_grade_code (grade_code)`
- 外键约束：
  - `fk_dim_grade_parent (parent_id -> dim_grade.id)`
- 业务约束：
  - `grade_type = stage` 时 `parent_id` 为空，`grade_type = grade` 时 `parent_id` 不为空
  - 年级节点必须挂在学段节点下，禁止年级节点继续挂载子年级节点

#### `dim_education_level`
学历层次维表，定义高中、专科、本科、硕士等学历层级。

- `junior_or_below`：初中及以下
- `senior_high`：高中
- `junior_college`：专科
- `bachelor`：本科
- `master`：硕士
- `doctor`：博士

- `id`：主键 ID。
- `level_code`：学历层次编码。
- `level_name`：学历层次名称。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_education_level_code (level_code)`
- 外键约束：
  - 无
- 业务约束：
  - 无

#### `dim_learning_goal`
学习目标维表，定义升学、就业、考证、兴趣提升等目标类型。

- `score_improvement`：提分提升
- `school_sync`：校内同步
- `exam_preparation`：升学备考
- `postgraduate_exam`：考研备考
- `certificate_exam`：考证取证
- `skill_improvement`：技能提升
- `job_hunting`：求职上岸
- `promotion`：岗位晋升
- `career_switch`：转岗转行
- `interest_learning`：兴趣学习
- `other`：其他

- `id`：主键 ID。
- `goal_code`：学习目标编码。
- `goal_name`：学习目标名称。
- `sort_no`：排序号。
- `yn`：是否启用，`1` 表示启用，`0` 表示停用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_dim_learning_goal_code (goal_code)`
- 外键约束：
  - 无
- 业务约束：
  - 无

### 用户与组织域
本域用于维护平台账号、机构组织、职员身份、负责人关系、教室资源和学员档案。

表说明：

- `sys_user`：平台账号主表，作为职员档案和学员档案的统一账号主体。
- `org_institution`：机构主表，定义学校、培训机构、教育品牌等办学主体。
- `org_campus`：校区表，定义机构下属校区或办学点。
- `org_department`：部门表，定义机构级或校区级部门组织结构。
- `org_staff_role`：机构职员角色表，定义每个机构自己的职员角色体系。
- `staff_profile`：职员档案表，定义某个平台账号在某个机构中的一份职员档案。
- `org_institution_manager`：机构负责人表，维护机构当前负责人关系。
- `org_campus_manager`：校区负责人表，维护校区当前负责人关系。
- `org_department_manager`：部门负责人表，维护部门当前负责人关系。
- `org_classroom`：教室资源表，统一管理线下教室和直播间资源。
- `student_profile`：学员档案表，定义平台级共享的学员档案。

依赖关系说明：

- `org_institution -> org_campus -> org_department` 构成组织层级主线。
- `org_staff_role` 依赖 `org_institution`，用于维护每个机构自己的职员角色体系。
- `staff_profile` 依赖 `sys_user`、`org_institution`、`org_campus`、`org_department`、`org_staff_role`。
- `org_institution_manager`、`org_campus_manager`、`org_department_manager` 都依赖 `staff_profile`，分别维护机构、校区、部门当前负责人的关系。
- `org_classroom` 依赖 `org_institution`，线下教室依赖 `org_campus`，直播间可不关联校区。
- `student_profile` 依赖 `sys_user` 以及学习者相关维表。

#### `sys_user`
平台账号主表，存储登录身份和个人基础信息。

- `id`：主键 ID。
- `nickname`：昵称。
- `real_name`：真实姓名。
- `mobile`：手机号。
- `email`：邮箱。
- `gender`：性别。
- `avatar_url`：头像地址。
- `birthday`：生日。
- `yn`：是否启用。
- `last_login_at`：最后登录时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_sys_user_mobile (mobile)`
  - `uk_sys_user_email (email)`
- 外键约束：
  - 无
- 业务约束：
  - 同一账号可同时关联 `staff_profile` 和 `student_profile`。
  - `created_at > birthday`
  - `updated_at >= created_at`
  - `last_login_at` 不为空时，`last_login_at > created_at`

#### `org_institution`
机构主表，定义学校、培训机构、教育品牌等办学主体信息。

- `id`：主键 ID。
- `institution_code`：机构编码。
- `institution_name`：机构名称。
- `institution_type`：机构类型。枚举值：
  - `training_center`：培训机构
  - `school`：学校
  - `education_brand`：教育品牌
  - `enterprise_academy`：企业培训中心
- `province`：省。
- `city`：市。
- `district`：区。
- `address`：详细地址。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_institution_code (institution_code)`
- 外键约束：
  - 无
- 业务约束：
  - `updated_at >= created_at`

#### `org_campus`
校区表，定义机构下属校区或办学点信息。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `campus_code`：校区编码。
- `campus_name`：校区名称。
- `province`：省。
- `city`：市。
- `district`：区。
- `address`：详细地址。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_campus_code (institution_id, campus_code)`
- 外键约束：
  - `fk_org_campus_institution (institution_id -> org_institution.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`

#### `org_department`
部门表，定义机构级或校区级的部门组织结构。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `campus_id`：校区ID，关联 `org_campus.id`。
- `parent_id`：父部门ID，关联 `org_department.id`。
- `dept_code`：部门编码。
- `dept_name`：部门名称。
- `sort_no`：排序号。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_department_code (institution_id, dept_code)`
- 外键约束：
  - `fk_org_department_institution (institution_id -> org_institution.id)`
  - `fk_org_department_campus (campus_id -> org_campus.id)`
  - `fk_org_department_parent (parent_id -> org_department.id)`
- 业务约束：
  - `campus_id` 允许为空，为空时表示机构级部门；不为空时表示校区级部门。
  - `parent_id` 对应的父部门必须与当前部门属于同一机构。
  - 父子部门的 `campus_id` 必须同时为空，或同时指向同一校区。
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `campus_id` 不为空时，`created_at >= org_campus.created_at`

#### `org_staff_role`
机构职员角色表，定义机构自有的职员角色体系。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `role_code`：职员角色编码。
- `role_name`：职员角色名称。
- `role_category`：角色类别。枚举值：
  - `teacher`：教师类
  - `academic`：教务类
  - `sales`：销售类
  - `operations`：运营类
  - `service`：服务类
  - `management`：管理类
- `sort_no`：排序号。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_staff_role_code (institution_id, role_code)`
- 外键约束：
  - `fk_org_staff_role_institution (institution_id -> org_institution.id)`
- 业务约束：
  - `role_category` 用于区分角色大类。
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`

#### `staff_profile`
职员档案表，定义教师、教务、销售、运营、客服等职员身份与组织归属。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `campus_id`：校区ID，关联 `org_campus.id`。
- `dept_id`：部门ID，关联 `org_department.id`。
- `staff_no`：职员编号。
- `staff_role_id`：职员角色ID，关联 `org_staff_role.id`。
- `teacher_intro`：教师介绍。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_staff_profile_no (institution_id, staff_no)`
  - `uk_staff_profile_user (institution_id, user_id)`
- 外键约束：
  - `fk_staff_profile_institution (institution_id -> org_institution.id)`
  - `fk_staff_profile_user (user_id -> sys_user.id)`
  - `fk_staff_profile_campus (campus_id -> org_campus.id)`
  - `fk_staff_profile_dept (dept_id -> org_department.id)`
  - `fk_staff_profile_role (staff_role_id -> org_staff_role.id)`
- 业务约束：
  - `user_id` 在同一机构内唯一，同一平台账号在每个机构内最多对应一条职员档案。
  - 机构级职员允许 `campus_id` 为空。
  - 校区级职员必须填写 `campus_id`。
  - `dept_id` 对应的部门必须与 `institution_id`、`campus_id` 保持一致。
  - `dept_id` 不为空时，若对应部门为机构级部门，则 `campus_id` 为空；若对应部门为校区级部门，则 `campus_id` 与部门归属校区一致。
  - `staff_role_id` 对应的角色必须与 `institution_id` 属于同一机构。
  - `staff_role_id` 对应角色为教师类岗位时，才填写 `teacher_intro`。
  - `staff_role_id` 对应角色为非教师类岗位时，`teacher_intro` 为空。
  - `updated_at >= created_at`
  - `created_at >= sys_user.created_at`
  - `created_at >= org_institution.created_at`

#### `org_institution_manager`
机构负责人表，维护当前生效的机构级负责人关系。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `staff_id`：负责人职员ID，关联 `staff_profile.id`。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_institution_manager_institution (institution_id)`
- 外键约束：
  - `fk_org_institution_manager_institution (institution_id -> org_institution.id)`
  - `fk_org_institution_manager_staff (staff_id -> staff_profile.id)`
- 业务约束：
  - `staff_id` 对应的职员档案必须与 `institution_id` 属于同一机构。
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= staff_profile.created_at`

#### `org_campus_manager`
校区负责人表，维护当前生效的校区级负责人关系。

- `id`：主键 ID。
- `campus_id`：校区ID，关联 `org_campus.id`。
- `staff_id`：负责人职员ID，关联 `staff_profile.id`。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_campus_manager_campus (campus_id)`
- 外键约束：
  - `fk_org_campus_manager_campus (campus_id -> org_campus.id)`
  - `fk_org_campus_manager_staff (staff_id -> staff_profile.id)`
- 业务约束：
  - 该表只维护当前生效的校区负责人关系，不维护历史版本。
  - `staff_id` 对应的职员档案必须与 `campus_id` 所属机构一致。
  - `staff_id` 对应的职员档案中的 `campus_id` 必须等于当前 `campus_id`。
  - `updated_at >= created_at`
  - `created_at >= org_campus.created_at`
  - `created_at >= staff_profile.created_at`

#### `org_department_manager`
部门负责人表，维护当前生效的部门级负责人关系。

- `id`：主键 ID。
- `department_id`：部门ID，关联 `org_department.id`。
- `staff_id`：负责人职员ID，关联 `staff_profile.id`。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_department_manager_department (department_id)`
- 外键约束：
  - `fk_org_department_manager_department (department_id -> org_department.id)`
  - `fk_org_department_manager_staff (staff_id -> staff_profile.id)`
- 业务约束：
  - `staff_id` 对应的职员档案必须与 `department_id` 所属机构一致。
  - `department_id` 对应部门存在 `campus_id` 时，`staff_id` 对应的职员档案中的 `campus_id` 必须等于该部门的 `campus_id`。
  - `updated_at >= created_at`
  - `created_at >= org_department.created_at`
  - `created_at >= staff_profile.created_at`

#### `org_classroom`
教室资源表，统一管理线下教室和直播间资源。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `campus_id`：校区ID，关联 `org_campus.id`。
- `room_code`：教室/直播间编码。
- `room_name`：教室/直播间名称。
- `room_type`：教室类型。枚举值：
  - `physical`：线下教室
  - `live`：直播间
- `max_capacity`：最大容量。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_org_classroom_code (institution_id, room_code)`
- 外键约束：
  - `fk_org_classroom_institution (institution_id -> org_institution.id)`
  - `fk_org_classroom_campus (campus_id -> org_campus.id)`
- 业务约束：
  - `room_type = physical` 时 `max_capacity` 必填，表示教室可容纳人数。
  - `room_type = physical` 时必须填写 `campus_id`，表示该教室归属具体校区。
  - `room_type = live` 时 `max_capacity` 可为空；若填写，则表示直播间最大在线人数上限。
  - `room_type = live` 时 `campus_id` 可为空；若填写，则表示该直播间由某个校区维护。
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `campus_id` 不为空时，`created_at >= org_campus.created_at`

#### `student_profile`
学员档案表，定义平台级学员身份、学习目标、学历层次、学业层级和画像信息，多个机构共享同一份学员档案。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `learner_identity_id`：学习者身份ID，关联 `dim_learner_identity.id`。
- `learning_goal_id`：学习目标ID，关联 `dim_learning_goal.id`。
- `education_level_id`：最高学历ID，关联 `dim_education_level.id`。
- `grade_id`：年级ID，关联 `dim_grade.id`。
- `school_name`：学校名称。
- `entrance_year`：入学年份。
- `industry_name`：所属行业。
- `job_role_name`：岗位角色。
- `career_stage`：职业阶段。
- `years_of_experience`：从业年限。
- `profile_note`：画像补充说明。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_student_profile_user (user_id)`
- 外键约束：
  - `fk_student_profile_user (user_id -> sys_user.id)`
  - `fk_student_profile_identity (learner_identity_id -> dim_learner_identity.id)`
  - `fk_student_profile_goal (learning_goal_id -> dim_learning_goal.id)`
  - `fk_student_profile_education (education_level_id -> dim_education_level.id)`
  - `fk_student_profile_grade (grade_id -> dim_grade.id)`
- 业务约束：
  - `user_id` 在学员档案中唯一，同一平台账号只维护一份学员档案。
  - `learner_identity_id` 对应在校生时，填写 `grade_id`，不填写 `education_level_id`。
  - `learner_identity_id` 对应非在校生时，填写 `education_level_id`，不填写 `grade_id`。
  - `school_name`、`entrance_year` 主要用于在校生场景。
  - `industry_name`、`job_role_name`、`career_stage`、`years_of_experience` 主要用于职场人和求职者场景。
  - `updated_at >= created_at`
  - `created_at >= sys_user.created_at`

### 课程域
本域用于维护课程产品、班次交付、课次安排和教学资源。

表说明：

- `series`：课程系列主表，定义课程产品主档。
- `series_category_rel`：课程系列分类关系表，定义课程系列与课程分类的映射关系。
- `series_cohort`：班次主表，定义课程系列的招生与交付期次。
- `series_cohort_course`：班次课程模块表，定义班次的课程模块和阶段顺序。
- `series_cohort_session`：课次主表，定义班次下的具体授课场次。
- `session_teacher_rel`：课次教师关系表，定义讲师、助教等授课角色。
- `session_asset`：课次资源表，统一管理讲义、练习、图片、视频等资源入口。
- `session_video`：课次视频表，维护视频元信息、转码状态、审核状态和发布时间。
- `session_video_chapter`：课次视频章节表，定义视频章节切片。
- `session_homework`：课次作业表，定义课次下布置的作业对象。
- `session_exam`：课次考试表，定义课次下的考试对象。

依赖关系说明：

- `series -> series_category_rel -> dim_course_category`：课程系列可关联一个或多个课程分类叶子节点。
- `series -> series_cohort`：课程系列可开设多个班次。
- `series_cohort -> series_cohort_course`：每个班次的课程模块与阶段安排。
- `series_cohort_course -> series_cohort_session`：班次课程模块进一步拆分为具体课次。
- `series_cohort_session -> session_teacher_rel`：课次关联讲师和助教等授课人员。
- `series_cohort_session -> session_asset -> session_video -> session_video_chapter`：课次资源中可包含视频资源，视频资源进一步拆分为视频章节。
- `series_cohort_session -> session_homework`：课次可布置作业。
- `series_cohort_session -> session_exam`：课次可配置考试。

#### `series`
课程系列主表，定义课程产品 SPU。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `delivery_mode`：授课方式。枚举值：
  - `online_live`：线上直播
  - `online_recorded`：线上录播
  - `offline_face_to_face`：线下面授
- `series_code`：课程系列编码。
- `series_name`：课程系列名称。
- `description`：课程系列描述。
- `cover_url`：封面图。
- `target_learner_identity_codes`：适用学员身份编码列表，JSON 字符串，对应 `dim_learner_identity.identity_code`。
- `target_learning_goal_codes`：适用学习目标编码列表，JSON 字符串，对应 `dim_learning_goal.goal_code`。
- `target_grade_codes`：适用学业层级编码列表，JSON 字符串，对应 `dim_grade.grade_code`。
- `sale_status`：售卖状态。枚举值：
  - `draft`：草稿
  - `on_sale`：在售
  - `off_sale`：下架
- `created_by`：创建人，关联 `sys_user.id`。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_series_code (institution_id, series_code)`
- 外键约束：
  - `fk_series_institution (institution_id -> org_institution.id)`
  - `fk_series_created_by (created_by -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= sys_user.created_at`
  - `target_learner_identity_codes` 不包含在校生类身份时，`target_grade_codes` 为空。
  - `target_learner_identity_codes` 与 `target_learning_goal_codes` 必须保持业务匹配，不允许出现身份与学习目标明显不相符的组合。

#### `series_category_rel`
课程系列分类关系表，定义课程系列与课程分类叶子节点的映射关系。

- `id`：主键 ID。
- `series_id`：课程系列ID，关联 `series.id`。
- `category_id`：课程分类ID，关联 `dim_course_category.id`。
- `sort_no`：排序号。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_series_category_rel (series_id, category_id)`
- 外键约束：
  - `fk_series_category_rel_series (series_id -> series.id)`
  - `fk_series_category_rel_category (category_id -> dim_course_category.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= series.created_at`
  - `category_id` 必须指向 `dim_course_category` 的叶子分类节点。

#### `series_cohort`
班次主表，定义课程系列的招生与交付期次 SKU。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `series_id`：课程系列ID，关联 `series.id`。
- `campus_id`：校区ID，关联 `org_campus.id`。
- `head_teacher_id`：班主任教师ID，关联 `staff_profile.id`。
- `cohort_code`：班次编码。
- `cohort_name`：班次名称。
- `sale_price`：班次售价。
- `max_student_count`：最大学员数。
- `current_student_count`：当前学员数。
- `yn`：是否启用。
- `start_date`：开放报名/学习开始日期。
- `end_date`：计划结班日期，仅直播班次和线下班次填写；录播班次为空。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_series_cohort_code (institution_id, cohort_code)`
- 外键约束：
  - `fk_series_cohort_institution (institution_id -> org_institution.id)`
  - `fk_series_cohort_series (series_id -> series.id)`
  - `fk_series_cohort_campus (campus_id -> org_campus.id)`
  - `fk_series_cohort_teacher (head_teacher_id -> staff_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= series.created_at`
  - `sale_price > 0`
  - 对应课程系列授课方式为 `online_live` 或 `offline_face_to_face` 时，`start_date` 表示开班日期，`end_date` 不为空，且 `start_date <= end_date`。
  - 对应课程系列授课方式为 `online_recorded` 时，`start_date` 表示开放报名/学习开始日期，`end_date` 为空。
  - `start_date >= DATE(created_at)`
  - `series_id` 对应的课程系列必须与 `institution_id` 属于同一机构。
  - 对应课程系列授课方式为 `offline_face_to_face` 时，`campus_id` 不为空，且对应校区必须与 `institution_id` 属于同一机构。
  - 对应课程系列授课方式为 `online_live` 或 `online_recorded` 时，`campus_id` 为空，班次不挂接具体校区或地址信息。
  - `head_teacher_id` 对应的职员档案必须与 `institution_id` 属于同一机构。
  - 对应课程系列授课方式为 `offline_face_to_face` 时，`head_teacher_id` 对应职员档案中的 `campus_id` 必须等于当前 `campus_id`。
  - 对应课程系列授课方式为 `online_live` 或 `online_recorded` 时，不校验 `head_teacher_id` 的校区归属，只要求同机构。
  - `head_teacher_id` 对应的职员角色必须属于教务类角色。

#### `series_cohort_course`
班次课程模块表，定义班次内自维护的课程模块和阶段顺序。

- `id`：主键 ID。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `module_code`：班次课程模块编码。
- `module_name`：班次课程模块名称。
- `description`：课程模块描述。
- `lesson_count`：总课时数。
- `total_hours`：总时长。
- `stage_no`：阶段序号。
- `start_date`：开始日期。
- `end_date`：结束日期。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_series_cohort_course_stage (cohort_id, stage_no)`
  - `uk_series_cohort_course_module (cohort_id, module_code)`
- 外键约束：
  - `fk_series_cohort_course_cohort (cohort_id -> series_cohort.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= series_cohort.created_at`
  - `start_date <= end_date`
  - `start_date >= series_cohort.start_date`
  - `series_cohort.end_date` 不为空时，`end_date <= series_cohort.end_date`

#### `series_cohort_session`
课次主表，定义班次下具体授课场次。

- `id`：主键 ID。
- `series_cohort_course_id`：班次课程模块ID，关联 `series_cohort_course.id`。
- `room_id`：教室资源ID，关联 `org_classroom.id`。
- `session_no`：课次序号。
- `session_title`：课次标题。
- `teaching_status`：授课状态。枚举值：
  - `scheduled`：待开课
  - `in_progress`：授课中
  - `completed`：已完成
  - `cancelled`：已取消
- `checkin_required`：是否需要签到。
- `teaching_date`：授课日期。
- `start_time`：开始时间；录播课次可为空。
- `end_time`：结束时间；录播课次可为空。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_series_cohort_session_no (series_cohort_course_id, session_no)`
- 外键约束：
  - `fk_series_cohort_session_course (series_cohort_course_id -> series_cohort_course.id)`
  - `fk_series_cohort_session_room (room_id -> org_classroom.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= series_cohort_course.created_at`
  - 对应课程系列授课方式为 `online_live` 或 `offline_face_to_face` 时，`start_time`、`end_time` 均不为空，且 `start_time < end_time`。
  - `teaching_date` 必须落在 `series_cohort_course.start_date` 与 `series_cohort_course.end_date` 之间；录播课中该字段表示内容发布时间。
  - `room_id` 不为空时，对应教室资源必须与 `series_cohort_course_id` 所属班次属于同一机构。
  - 对应课程系列授课方式为 `offline_face_to_face` 时，`room_id` 必填，且 `room_id` 对应资源的 `room_type = physical`。
  - 对应课程系列授课方式为 `online_live` 时，`room_id` 必填，且 `room_id` 对应资源的 `room_type = live`。
  - 对应课程系列授课方式为 `online_recorded` 时，`checkin_required = 0`，`room_id` 为空，`start_time`、`end_time` 为空。

#### `session_teacher_rel`
课次教师关系表，定义课次关联的授课教师。

- `id`：主键 ID。
- `session_id`：课次ID，关联 `series_cohort_session.id`。
- `teacher_id`：教师档案ID，关联 `staff_profile.id`。
- `sort_no`：排序号。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_teacher_rel (session_id, teacher_id)`
- 外键约束：
  - `fk_session_teacher_rel_session (session_id -> series_cohort_session.id)`
  - `fk_session_teacher_rel_teacher (teacher_id -> staff_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= series_cohort_session.created_at`
  - `created_at >= staff_profile.created_at`
  - `teacher_id` 对应的职员档案必须与 `session_id` 所属班次属于同一机构。
  - `teacher_id` 对应的职员角色必须属于教师类角色。

#### `session_asset`
课次资源表，统一管理讲义、练习、参考资料、图片和视频资源入口。

- `id`：主键 ID。
- `session_id`：所属课次ID，关联 `series_cohort_session.id`。
- `asset_code`：课次资源编码。
- `asset_name`：资源名称。
- `file_type`：文件格式类型，存储文件扩展名，如 `pdf`、`docx`、`mp4`、`jpg`、`zip`。
- `material_category`：资料业务类别。枚举值：
  - `video`：视频
  - `handout`：讲义
  - `exercise`：练习
  - `reference`：参考资料
  - `image`：图片
- `sort_no`：排序号。
- `access_scope`：访问范围。枚举值：
  - `public`：公开可见
  - `trial`：试听可见
  - `enrolled_only`：仅已报名学员可见
  - `internal_only`：仅内部人员可见
- `file_url`：文件地址，非空。
- `file_size`：文件大小。
- `uploader_user_id`：上传人，关联 `sys_user.id`。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_asset_code (session_id, asset_code)`
- 外键约束：
  - `fk_session_asset_session (session_id -> series_cohort_session.id)`
  - `fk_session_asset_uploader (uploader_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= series_cohort_session.created_at`
  - `created_at >= sys_user.created_at`
  - `file_size >= 0`

#### `session_video`
课次视频表，定义视频元信息、转码状态、审核状态和发布时间。

- `id`：主键 ID。
- `asset_id`：课次资源ID，关联 `session_asset.id`。
- `video_code`：视频编码。
- `video_title`：视频标题。
- `cover_url`：封面地址。
- `duration_seconds`：视频时长，单位：秒。
- `resolution_label`：分辨率标识。
- `bitrate_kbps`：码率kbps。
- `transcode_status`：转码状态。枚举值：
  - `pending`：待转码
  - `in_progress`：转码中
  - `completed`：转码完成
  - `failed`：转码失败
- `review_status`：审核状态。枚举值：
  - `pending`：待审核
  - `approved`：已通过
  - `rejected`：已驳回
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_video_code (asset_id, video_code)`
- 外键约束：
  - `fk_session_video_asset (asset_id -> session_asset.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= session_asset.created_at`
  - `asset_id` 对应的课次资源的 `material_category` 必须为 `video`。
  - `asset_id` 对应的课次资源的 `file_type` 必须为视频文件扩展名，如 `mp4`、`mov`、`avi`、`mkv`。
  - `duration_seconds > 0`
  - `bitrate_kbps > 0`

#### `session_video_chapter`
课次视频章节表，定义视频章节切片。

- `id`：主键 ID。
- `video_id`：课次视频ID，关联 `session_video.id`。
- `chapter_no`：章节序号。
- `chapter_title`：章节标题。
- `start_second`：开始秒数。
- `end_second`：结束秒数。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_video_chapter_no (video_id, chapter_no)`
- 外键约束：
  - `fk_session_video_chapter_video (video_id -> session_video.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= session_video.created_at`
  - `start_second < end_second`
  - `start_second >= 0`
  - `end_second <= session_video.duration_seconds`

#### `session_homework`
课次作业表，定义课次下布置的作业对象。

- `id`：主键 ID。
- `session_id`：所属课次ID，关联 `series_cohort_session.id`。
- `homework_code`：作业编码。
- `homework_name`：作业名称。
- `created_by`：创建人，关联 `staff_profile.id`。
- `due_at`：截止时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_homework_code (session_id, homework_code)`
- 外键约束：
  - `fk_session_homework_session (session_id -> series_cohort_session.id)`
  - `fk_session_homework_created_by (created_by -> staff_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= series_cohort_session.created_at`
  - `created_by` 对应的职员档案必须与 `session_id` 所属班次属于同一机构。
  - `due_at >= created_at`
  - 仅对 `online_live`、`offline_face_to_face` 课次生成固定截止时间作业；`online_recorded` 课次不在供给层生成固定截止时间作业。

#### `session_exam`
课次考试表，定义课次下的考试对象。

- `id`：主键 ID。
- `session_id`：所属课次ID，关联 `series_cohort_session.id`。
- `exam_code`：考试编码。
- `exam_name`：考试名称。
- `total_score`：总分。
- `pass_score`：及格分。
- `publish_status`：发布状态。枚举值：
  - `draft`：草稿
  - `published`：已发布
  - `closed`：已关闭
- `created_by`：创建人，关联 `staff_profile.id`。
- `duration_minutes`：考试时长。
- `window_start_at`：起始时间。
- `deadline_at`：截止时间。
- `publish_at`：发布时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_exam_code (session_id, exam_code)`
- 外键约束：
  - `fk_session_exam_session (session_id -> series_cohort_session.id)`
  - `fk_session_exam_created_by (created_by -> staff_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= series_cohort_session.created_at`
  - `created_by` 对应的职员档案必须与 `session_id` 所属班次属于同一机构。
  - `total_score > 0`
  - `pass_score >= 0`
  - `pass_score <= total_score`
  - `duration_minutes > 0`
  - `publish_at` 不为空时，`publish_at >= created_at`
  - `window_start_at <= deadline_at`
  - `TIMESTAMPDIFF(MINUTE, window_start_at, deadline_at) >= duration_minutes`
  - `publish_status = published` 时，`publish_at` 不为空。
  - 仅对 `online_live`、`offline_face_to_face` 课次生成固定考试窗口；`online_recorded` 课次不在供给层生成固定考试窗口。

### 题库域
本域用于维护机构题库、题目主数据，以及作业和考试引用题目的关系。

表说明：

- `question_bank`：题库主表，定义机构题库和所属课程分类。
- `question`：题目主表，定义题型、题干、选项、答案和解析。
- `session_homework_question_rel`：作业题目关系表，定义作业包含的题目与题目分值。
- `session_exam_question_rel`：考试题目关系表，定义考试包含的题目与题目分值。

依赖关系说明：

- `question_bank -> question`：题库下维护多道题目。
- `question -> dim_question_type`：题目挂接题型维表。
- `question_bank`、`question` 均可挂接 `dim_course_category`，用于题库和题目的课程分类归属。
- `session_homework -> session_homework_question_rel -> question`：作业通过关系表引用题目。
- `session_exam -> session_exam_question_rel -> question`：考试通过关系表引用题目。

#### `question_bank`
题库主表，定义机构题库和所属分类层级。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `category_id`：课程分类ID，关联 `dim_course_category.id`。
- `bank_code`：题库编码。
- `bank_name`：题库名称。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_question_bank_code (institution_id, bank_code)`
- 外键约束：
  - `fk_question_bank_institution (institution_id -> org_institution.id)`
  - `fk_question_bank_category (category_id -> dim_course_category.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `category_id` 必须指向 `dim_course_category` 的叶子分类节点。

#### `question`
题目主表，定义题型、题干、选项、答案和解析。

- `id`：主键 ID。
- `bank_id`：题库ID，关联 `question_bank.id`。
- `question_code`：题目编码。
- `question_type_id`：题型ID，关联 `dim_question_type.id`。
- `stem`：题干，非空。
- `options_json`：选项JSON。
- `answer_text`：参考答案，非空。
- `analysis_text`：解析。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_question_code (bank_id, question_code)`
- 外键约束：
  - `fk_question_bank (bank_id -> question_bank.id)`
  - `fk_question_type (question_type_id -> dim_question_type.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= question_bank.created_at`
  - 选择类题型必须填写 `options_json`，非选择类题型 `options_json` 为空。

#### `session_homework_question_rel`
作业题目关系表，定义作业包含的题目与题目分值。

- `id`：主键 ID。
- `homework_id`：作业ID。
- `question_id`：题目ID。
- `sort_no`：排序号。
- `score`：题目分值。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_homework_question_rel (homework_id, question_id)`
  - `uk_session_homework_question_sort (homework_id, sort_no)`
- 外键约束：
  - `fk_session_homework_question_rel_homework (homework_id -> session_homework.id)`
  - `fk_session_homework_question_rel_question (question_id -> question.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `score > 0`
  - `created_at >= session_homework.created_at`
  - `created_at >= question.created_at`
  - `question_id` 对应题目所属机构必须与 `homework_id` 所属班次机构一致。

#### `session_exam_question_rel`
考试题目关系表，定义考试包含的题目与题目分值。

- `id`：主键 ID。
- `exam_id`：考试ID。
- `question_id`：题目ID。
- `sort_no`：排序号。
- `score`：题目分值。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_exam_question_rel (exam_id, question_id)`
  - `uk_session_exam_question_sort (exam_id, sort_no)`
- 外键约束：
  - `fk_session_exam_question_rel_exam (exam_id -> session_exam.id)`
  - `fk_session_exam_question_rel_question (question_id -> question.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `score > 0`
  - `created_at >= session_exam.created_at`
  - `created_at >= question.created_at`
  - `question_id` 对应题目所属机构必须与 `exam_id` 所属班次机构一致。
  - 同一考试下所有题目 `score` 之和必须等于 `session_exam.total_score`。

### 营销域
本域用于维护优惠券模板和优惠券适用范围。

表说明：

- `coupon`：优惠券主表，定义平台券和机构券模板。
- `coupon_category_rel`：优惠券分类适用范围关系表，定义优惠券可作用的课程分类。
- `coupon_series_rel`：优惠券课程系列适用范围关系表，定义优惠券可作用的课程系列。

依赖关系说明：

- `coupon -> org_institution`：机构券挂接机构，平台券不挂接机构。
- `coupon -> coupon_category_rel -> dim_course_category`：优惠券可限定适用课程分类。
- `coupon -> coupon_series_rel -> series`：优惠券可限定适用课程系列。

#### `coupon`
优惠券主表，定义平台券和机构券模板。

- `id`：主键 ID。
- `institution_id`：机构ID，机构券时有值，关联 `org_institution.id`。
- `issuer_scope`：发券主体范围。枚举值：
  - `platform`：平台券
  - `institution`：机构券
- `coupon_code`：优惠券编码。
- `coupon_name`：优惠券名称。
- `coupon_type`：优惠券类型。枚举值：
  - `cash`：满减券
  - `discount`：折扣券
  - `trial`：试听券
  - `gift`：赠课券
- `discount_amount`：优惠金额。
- `discount_rate`：折扣比例。
- `threshold_amount`：使用门槛。
- `total_count`：发放总量。
- `per_user_limit`：单用户可领取上限。
- `receive_count`：领取数量。
- `used_count`：已使用数量。
- `yn`：是否启用。
- `valid_from`：生效时间。
- `valid_to`：失效时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_coupon_code (coupon_code)`
- 外键约束：
  - `fk_coupon_institution (institution_id -> org_institution.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `issuer_scope = platform` 时，`institution_id` 为空。
  - `issuer_scope = institution` 时，`institution_id` 不为空。
  - `institution_id` 不为空时，`created_at >= org_institution.created_at`
  - 现金券填写 `discount_amount`，`discount_rate` 为空。
  - 折扣券填写 `discount_rate`，`discount_amount` 为空。
  - `discount_amount` 不为空时，`discount_amount > 0`。
  - `discount_rate` 不为空时，`discount_rate > 0 and discount_rate < 1`。
  - `threshold_amount >= 0`
  - `per_user_limit > 0`
  - `total_count >= receive_count`
  - `receive_count >= used_count`
  - `valid_from <= valid_to`
  - `valid_from >= created_at`

#### `coupon_category_rel`
优惠券分类适用范围关系表，定义优惠券可作用的课程分类。

- `id`：主键 ID。
- `coupon_id`：优惠券ID，关联 `coupon.id`。
- `category_id`：课程分类ID，关联 `dim_course_category.id`。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_coupon_category_rel (coupon_id, category_id)`
- 外键约束：
  - `fk_coupon_category_rel_coupon (coupon_id -> coupon.id)`
  - `fk_coupon_category_rel_category (category_id -> dim_course_category.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= coupon.created_at`
  - `category_id` 必须指向 `dim_course_category` 的叶子分类节点。

#### `coupon_series_rel`
优惠券课程系列适用范围关系表，定义优惠券可作用的课程系列。

- `id`：主键 ID。
- `coupon_id`：优惠券ID，关联 `coupon.id`。
- `series_id`：课程系列ID，关联 `series.id`。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_coupon_series_rel (coupon_id, series_id)`
- 外键约束：
  - `fk_coupon_series_rel_coupon (coupon_id -> coupon.id)`
  - `fk_coupon_series_rel_series (series_id -> series.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= coupon.created_at`
  - `created_at >= series.created_at`
  - `coupon_id` 对应优惠券为机构券时，`series_id` 对应课程系列必须与优惠券属于同一机构。

### 转化域
本域用于维护用户线上曝光、访问、搜索、收藏、购物车、咨询和领券等转化行为。

表说明：

- `series_exposure_log`：课程系列曝光日志表，记录课程在列表页、活动页、搜索结果页等线上页面场景的曝光行为。
- `series_visit_log`：课程系列访问日志表，记录课程详情页访问行为。
- `series_search_log`：课程搜索日志表，记录搜索关键词、结果数和点击结果。
- `series_favorite`：课程系列收藏表，记录用户对课程系列的收藏关系。
- `shopping_cart_item`：购物车明细表，记录用户加入购物车的班次商品。
- `consultation_record`：咨询记录表，记录售前咨询过程。
- `coupon_receive_record`：领券记录表，记录用户领取、使用和过期的券实例。

依赖关系说明：

- `series_exposure_log -> series_visit_log`：访问日志可通过 `ref_exposure_id` 关联来源曝光记录，表示从曝光到访问的转化。
- `series_search_log` 与曝光、访问日志属于并列行为日志，独立记录用户搜索和搜索结果点击行为。
- `series_favorite`、`shopping_cart_item` 均围绕 `sys_user` 和 `series` 或 `series_cohort` 记录用户意向。
- `consultation_record -> dim_channel`：咨询记录承接机构招生渠道，作为获客归因主口径。
- `coupon -> coupon_receive_record`：优惠券模板领取后形成用户领券记录，后续可进入交易优惠链路。

#### `series_exposure_log`
课程系列曝光日志表，记录课程在列表页、活动页、搜索结果页等线上页面场景的曝光行为。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `series_id`：课程系列ID，关联 `series.id`。
- `exposure_scene`：曝光场景。枚举值：
  - `recommendation`：推荐场景
  - `search`：搜索场景
  - `activity`：活动场景
  - `category`：分类浏览场景
  - `learning_center`：学习中心场景
- `position_no`：曝光位序号。
- `device_type`：设备类型。
- `exposed_at`：曝光时间。
- `created_at`：创建时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_series_exposure_log_user (user_id -> sys_user.id)`
  - `fk_series_exposure_log_series (series_id -> series.id)`
- 业务约束：
  - `created_at >= sys_user.created_at`
  - `created_at >= series.created_at`
  - `exposed_at >= created_at`

#### `series_visit_log`
课程系列访问日志表，记录课程详情页访问行为。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `series_id`：课程系列ID，关联 `series.id`。
- `ref_exposure_id`：来源曝光日志ID，关联 `series_exposure_log.id`。
- `visit_source`：访问来源。枚举值：
  - `recommendation`：推荐列表
  - `search_result`：搜索结果
  - `activity_page`：活动页
  - `favorite_list`：收藏列表
  - `shopping_cart`：购物车
  - `direct_access`：直接访问
- `stay_seconds`：停留时长，单位：秒。
- `enter_at`：进入时间。
- `leave_at`：离开时间。
- `created_at`：创建时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_series_visit_log_user (user_id -> sys_user.id)`
  - `fk_series_visit_log_series (series_id -> series.id)`
  - `fk_series_visit_log_exposure (ref_exposure_id -> series_exposure_log.id)`
- 业务约束：
  - `created_at >= sys_user.created_at`
  - `created_at >= series.created_at`
  - `ref_exposure_id` 不为空时，来源曝光记录的 `series_id` 必须等于当前 `series_id`。
  - `ref_exposure_id` 不为空时，来源曝光记录的 `user_id` 必须等于当前 `user_id`。
  - `enter_at >= created_at`
  - `leave_at` 不为空时，`leave_at >= enter_at`
  - `stay_seconds >= 0`

#### `series_search_log`
课程搜索日志表，记录搜索关键词、结果数和点击结果。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `keyword_text`：搜索关键词，非空。
- `search_source`：搜索来源。枚举值：
  - `home_page`：首页搜索
  - `course_list_page`：课程列表页搜索
  - `category_page`：分类页搜索
  - `learning_center`：学习中心搜索
- `result_count`：结果数。
- `clicked_series_id`：点击课程系列ID，关联 `series.id`。
- `searched_at`：搜索时间。
- `created_at`：创建时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_series_search_log_user (user_id -> sys_user.id)`
  - `fk_series_search_log_series (clicked_series_id -> series.id)`
- 业务约束：
  - `created_at >= sys_user.created_at`
  - `searched_at >= created_at`
  - `result_count >= 0`
  - `clicked_series_id` 不为空时，`result_count > 0`
  - `clicked_series_id` 不为空时，点击课程系列必须来自本次搜索结果。

#### `series_favorite`
课程系列收藏表，记录用户对课程系列的收藏关系。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `series_id`：课程系列ID，关联 `series.id`。
- `favorite_source`：收藏来源。枚举值：
  - `series_detail`：课程详情页
  - `search_result`：搜索结果页
  - `recommendation`：推荐列表
  - `activity_page`：活动页
- `yn`：是否有效。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_series_favorite (user_id, series_id)`
- 外键约束：
  - `fk_series_favorite_user (user_id -> sys_user.id)`
  - `fk_series_favorite_series (series_id -> series.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= sys_user.created_at`
  - `created_at >= series.created_at`

#### `shopping_cart_item`
购物车明细表，记录用户加入购物车的班次商品。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `unit_price`：单价。
- `cart_source`：加入来源。枚举值：
  - `series_detail`：课程详情页
  - `search_result`：搜索结果页
  - `recommendation`：推荐列表
  - `activity_page`：活动页
- `added_at`：加入时间。
- `removed_at`：移除时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_shopping_cart_item (user_id, cohort_id)`
- 外键约束：
  - `fk_shopping_cart_item_user (user_id -> sys_user.id)`
  - `fk_shopping_cart_item_cohort (cohort_id -> series_cohort.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= sys_user.created_at`
  - `created_at >= series_cohort.created_at`
  - `unit_price >= 0`
  - `added_at >= created_at`
  - `removed_at` 不为空时，`removed_at >= added_at`

#### `consultation_record`
咨询记录表，记录售前咨询过程。

- `id`：主键 ID。
- `user_id`：用户ID，关联 `sys_user.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `consultant_user_id`：顾问用户ID，关联 `sys_user.id`。
- `source_channel_id`：来源渠道ID，关联 `dim_channel.id`。
- `consult_channel`：咨询渠道。枚举值：
  - `phone`：电话
  - `online_chat`：在线咨询
  - `wechat`：微信
  - `offline_visit`：到店咨询
- `contact_mobile`：咨询人联系电话，非空。
- `consult_content`：咨询内容。
- `consulted_at`：咨询时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_consultation_user (user_id -> sys_user.id)`
  - `fk_consultation_cohort (cohort_id -> series_cohort.id)`
  - `fk_consultation_consultant (consultant_user_id -> sys_user.id)`
  - `fk_consultation_source_channel (source_channel_id -> dim_channel.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= sys_user.created_at`
  - `created_at >= series_cohort.created_at`
  - `consultant_user_id` 对应用户必须存在职员档案，且职员档案与 `cohort_id` 所属机构一致。
  - `consulted_at >= created_at`

#### `coupon_receive_record`
领券记录表，记录用户领取、使用和过期的券实例。

- `id`：主键 ID。
- `coupon_id`：优惠券ID，关联 `coupon.id`。
- `user_id`：用户ID，关联 `sys_user.id`。
- `receive_no`：领券编号。
- `receive_source`：领券来源。枚举值：
  - `coupon_center`：领券中心
  - `activity_page`：活动页
  - `series_detail`：课程详情页
  - `order_settlement`：订单结算页
  - `consultation`：咨询转化
- `receive_status`：领券状态。枚举值：
  - `unused`：未使用
  - `used`：已使用
  - `expired`：已过期
- `yn`：是否有效。
- `received_at`：领取时间。
- `used_at`：使用时间。
- `expired_at`：过期时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_coupon_receive_record_no (receive_no)`
- 外键约束：
  - `fk_coupon_receive_record_coupon (coupon_id -> coupon.id)`
  - `fk_coupon_receive_record_user (user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= coupon.created_at`
  - `created_at >= sys_user.created_at`
  - `received_at >= created_at`
  - `expired_at > received_at`
  - `used_at` 不为空时，`used_at >= received_at`
  - `used_at` 不为空时，`used_at <= expired_at`
  - `receive_status = unused` 时，`used_at` 为空。
  - `receive_status = used` 时，`used_at` 不为空。
  - 同一 `(coupon_id, user_id)` 的领券记录数量不得超过 `coupon.per_user_limit`。
  - `receive_status = expired` 时，`used_at` 为空，且 `expired_at <= updated_at`。

### 交易域
本域用于维护订单、订单明细、支付流水和退款申请。

表说明：

- `order`：订单主表，记录用户下单、支付和退款汇总信息。
- `order_item`：订单明细表，记录订单下实际成交的班次商品。
- `payment_record`：支付记录表，记录支付流水、支付渠道、支付状态和累计退款金额。
- `refund_request`：退款申请表，记录订单或订单明细级退费申请和审批结果。

依赖关系说明：

- `order -> order_item`：订单下拆分实际成交的班次商品明细。
- `order -> payment_record`：订单支付产生支付流水。
- `order / order_item / payment_record -> refund_request`：退款申请关联订单、订单明细和支付记录。
- `coupon_receive_record -> order`：用户领券记录可进入订单优惠链路。

#### `order`
订单主表，记录用户下单、支付和退款汇总信息。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `order_no`：订单号。
- `user_id`：下单用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `coupon_receive_record_id`：领券记录ID，关联 `coupon_receive_record.id`。
- `order_source_channel_id`：订单来源渠道ID，关联 `dim_channel.id`。该字段由系统自动归因写入，正常站内自然下单时可为空。
- `order_status`：订单状态。枚举值：
  - `pending`：待支付
  - `paid`：已支付
  - `completed`：已完结
  - `cancelled`：已取消
  - `partial_refunded`：部分退款
  - `refunded`：已退款
- `total_amount`：订单总额。
- `discount_amount`：优惠金额。
- `payable_amount`：应付金额。
- `paid_amount`：实付金额。
- `refund_amount`：累计退款金额，冗余汇总字段。
- `remark`：用户下单备注，由用户在提交订单时主动填写；未填写时为空。
- `paid_at`：支付时间。
- `cancel_at`：取消时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_order_no (institution_id, order_no)`
- 外键约束：
  - `fk_order_institution (institution_id -> org_institution.id)`
  - `fk_order_user (user_id -> sys_user.id)`
  - `fk_order_student (student_id -> student_profile.id)`
  - `fk_order_coupon_receive_record (coupon_receive_record_id -> coupon_receive_record.id)`
  - `fk_order_source_channel (order_source_channel_id -> dim_channel.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= sys_user.created_at`
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `institution_id` 必须与订单实际成交商品所属机构一致。
  - `order_source_channel_id` 不允许由用户在下单页手工选择；创建订单接口可接收调用程序传入的系统归因结果。
  - `order_source_channel_id` 可为空；为空时表示本次订单未命中明确渠道归因，或用户直接在应用内自然浏览、搜索、加购后完成下单。
  - `order_source_channel_id` 不为空时，必须关联有效的 `dim_channel` 渠道记录。
  - 订单由咨询记录转化时，`order_source_channel_id` 必须等于对应 `consultation_record.source_channel_id`。
  - 订单由落地页、投放链接、活动页二维码、私域分享链接或其他归因链路转化时，`order_source_channel_id` 必须由系统继承对应渠道来源。
  - 同一订单同时存在多个可归因来源时，固定按最近一次有效归因链路或咨询归因主链路写入一条渠道记录，不重复写入多个渠道。
  - 同一订单一旦写入 `order_source_channel_id`，后续不得因页面跳转、站内二次访问或下单页刷新改写渠道归因结果。
  - `coupon_receive_record_id` 不为空时，对应优惠券模板为机构券时，其 `institution_id` 必须等于当前 `institution_id`；为平台券时可为空。
  - `total_amount >= 0`
  - `discount_amount >= 0`
  - `paid_amount` 不为空时，`paid_amount >= 0`。
  - `refund_amount` 不为空时，`refund_amount >= 0`。
  - `discount_amount <= total_amount`
  - `payable_amount = total_amount - discount_amount`
  - `paid_amount` 不为空时，`paid_amount <= payable_amount`。
  - `refund_amount` 不为空时，`paid_amount` 必须不为空，且 `refund_amount <= paid_amount`。
  - `coupon_receive_record_id` 不为空时，对应领券记录必须属于当前 `user_id`。
  - `coupon_receive_record_id` 不为空时，对应领券记录在创建订单前必须为未使用且未过期状态。
  - `coupon_receive_record_id` 不为空且订单支付成功后，必须将对应领券记录更新为已使用状态，并写入 `coupon_receive_record.used_at = paid_at`。
  - `coupon_receive_record_id` 不为空且订单未支付取消时，对应领券记录保持未使用状态。
  - `paid_at` 不为空时，`paid_at >= created_at`。
  - `cancel_at` 不为空时，`cancel_at >= created_at`。
  - `paid_at` 与 `cancel_at` 不能同时有值。
  - `order_status = pending` 时，`paid_at`、`cancel_at`、`paid_amount`、`refund_amount` 为空。
  - `order_status = paid` 时，`paid_at` 不为空，`cancel_at` 为空，`paid_amount = payable_amount`，`refund_amount` 为空。
  - `order_status = completed` 时，`paid_at` 不为空，`cancel_at` 为空，`paid_amount = payable_amount`，`refund_amount` 为空。
  - `order_status = cancelled` 时，`cancel_at` 不为空，`paid_at`、`paid_amount`、`refund_amount` 为空。
  - `order_status = partial_refunded` 时，`paid_at` 不为空，`paid_amount = payable_amount`，且 `0 < refund_amount < paid_amount`。
  - `order_status = refunded` 时，`paid_at` 不为空，`paid_amount = payable_amount`，且 `refund_amount = paid_amount`。

#### `order_item`
订单明细表，记录订单下实际成交的班次商品。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `order_id`：订单ID，关联 `order.id`。
- `user_id`：下单用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `order_item_status`：订单明细状态。枚举值：
  - `pending`：待支付
  - `paid`：已支付
  - `completed`：已完结
  - `cancelled`：已取消
  - `refunded`：已退款
- `item_name`：商品名称，非空。
- `unit_price`：单价。
- `discount_amount`：优惠金额。
- `payable_amount`：应付金额。
- `service_period_days`：服务周期天数。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_order_item_institution (institution_id -> org_institution.id)`
  - `fk_order_item_order (order_id -> order.id)`
  - `fk_order_item_user (user_id -> sys_user.id)`
  - `fk_order_item_student (student_id -> student_profile.id)`
  - `fk_order_item_cohort (cohort_id -> series_cohort.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= order.created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= sys_user.created_at`
  - `created_at >= series_cohort.created_at`
  - `institution_id` 必须等于 `order_id` 对应订单的 `institution_id`。
  - `user_id` 必须等于 `order_id` 对应订单的 `user_id`。
  - `student_id` 必须等于 `order_id` 对应订单的 `student_id`。
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `cohort_id` 对应班次必须属于 `institution_id`。
  - `cohort_id` 对应班次必须与 `order_id` 使用的优惠券适用范围保持一致。
  - `unit_price >= 0`
  - `discount_amount >= 0`
  - `discount_amount <= unit_price`
  - `payable_amount = unit_price - discount_amount`
  - `service_period_days > 0`
  - `order_item_status` 必须与 `order_id` 对应订单状态保持一致或更细粒度一致，不允许出现订单已取消但订单明细已完成等冲突状态。

#### `payment_record`
支付记录表，记录支付流水、支付渠道、支付状态和累计退款金额。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `order_id`：订单ID，关联 `order.id`。
- `payment_no`：支付流水号。
- `payment_channel`：支付渠道。枚举值：
  - `wechat_pay`：微信支付
  - `alipay`：支付宝
  - `bank_card`：银行卡
  - `offline_transfer`：线下转账
  - `public_account`：对公转账
  - `campus_cashier`：校区收银
- `payment_status`：支付状态。枚举值：
  - `pending`：待支付
  - `paid`：已支付
  - `failed`：支付失败
  - `closed`：已关闭
  - `partial_refunded`：部分退款
  - `refunded`：已退款
- `amount`：支付金额。
- `third_party_trade_no`：第三方交易号。
- `refund_amount`：累计退款金额，冗余汇总字段。
- `paid_at`：支付时间。
- `refund_at`：退款时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_payment_record_no (institution_id, payment_no)`
- 外键约束：
  - `fk_payment_record_institution (institution_id -> org_institution.id)`
  - `fk_payment_record_order (order_id -> order.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= order.created_at`
  - `institution_id` 必须等于 `order_id` 对应订单的 `institution_id`。
  - `amount >= 0`
  - `refund_amount` 不为空时，`refund_amount >= 0`。
  - `amount` 必须等于 `order_id` 对应订单的 `payable_amount`。
  - `refund_amount` 不为空时，`refund_amount <= amount`。
  - `paid_at` 不为空时，`paid_at >= created_at`。
  - `refund_at` 不为空时，`refund_at >= created_at`。
  - `refund_at` 不为空时，`paid_at` 必须不为空，且 `refund_at >= paid_at`。
  - `payment_status = pending` 时，`paid_at`、`refund_at`、`refund_amount` 为空。
  - `payment_status = paid` 时，`paid_at` 不为空，`refund_at`、`refund_amount` 为空。
  - `payment_status = failed` 时，`paid_at`、`refund_at`、`refund_amount` 为空。
  - `payment_status = closed` 时，`paid_at`、`refund_at`、`refund_amount` 为空。
  - `payment_status = partial_refunded` 时，`paid_at` 不为空，`refund_at` 不为空，且 `0 < refund_amount < amount`。
  - `payment_status = refunded` 时，`paid_at` 不为空，`refund_at` 不为空，且 `refund_amount = amount`。
  - `payment_status` 必须与 `order_id` 对应订单状态保持一致，不允许出现支付已退款但订单仍为待支付等冲突状态。

#### `refund_request`
退款申请表，记录订单或订单明细级退费申请和审批结果。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `refund_no`：退费申请编号。
- `order_id`：订单ID，关联 `order.id`。
- `order_item_id`：订单明细ID，关联 `order_item.id`。
- `payment_id`：支付记录ID，关联 `payment_record.id`。
- `user_id`：申请用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `refund_type`：退费类型。枚举值：
  - `personal_reason`：个人原因
  - `course_unsatisfied`：课程不满意
  - `schedule_conflict`：时间冲突
  - `duplicate_purchase`：重复购买
- `refund_reason`：退费原因，非空。
- `refund_status`：退费状态。枚举值：
  - `pending`：待审批
  - `approved`：已通过
  - `rejected`：已驳回
  - `refunded`：已退款
- `apply_amount`：申请退费金额。
- `approved_amount`：审批退费金额(退费主口径)。
- `approver_user_id`：审批人用户ID，关联 `sys_user.id`。
- `remark`：退费处理备注，由审批人或客服在审核、驳回、退款处理时填写；无额外说明时为空。
- `yn`：是否有效。
- `applied_at`：申请时间。
- `approved_at`：审批时间。
- `refunded_at`：到账时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_refund_request_no (institution_id, refund_no)`
- 外键约束：
  - `fk_refund_request_institution (institution_id -> org_institution.id)`
  - `fk_refund_request_order (order_id -> order.id)`
  - `fk_refund_request_order_item (order_item_id -> order_item.id)`
  - `fk_refund_request_payment (payment_id -> payment_record.id)`
  - `fk_refund_request_user (user_id -> sys_user.id)`
  - `fk_refund_request_student (student_id -> student_profile.id)`
  - `fk_refund_request_approver (approver_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= order.created_at`
  - `created_at >= sys_user.created_at`
  - `institution_id` 必须等于 `order_id` 对应订单的 `institution_id`。
  - `user_id` 必须等于 `order_id` 对应订单的 `user_id`。
  - `student_id` 必须等于 `order_id` 对应订单的 `student_id`。
  - `order_item_id` 必须属于 `order_id`。
  - `payment_id` 必须属于 `order_id`。
  - `payment_id` 对应支付记录必须为已支付、部分退款或已退款状态。
  - `refund_type` 必须与 `order_item_id` 对应商品实际支持的退费场景一致。
  - `apply_amount > 0`
  - `approved_amount` 不为空时，`approved_amount >= 0`。
  - `apply_amount <= payment_id` 对应支付记录的可退余额。
  - `approved_amount` 不为空时，`approved_amount <= apply_amount`。
  - `applied_at >= created_at`
  - `approved_at` 不为空时，`approved_at >= applied_at`。
  - `refunded_at` 不为空时，`approved_at` 必须不为空，且 `refunded_at >= approved_at`。
  - `refund_status = pending` 时，`approved_amount`、`approved_at`、`refunded_at` 为空。
  - `refund_status = approved` 时，`approved_amount` 不为空，`approved_at` 不为空，`refunded_at` 为空。
  - `refund_status = rejected` 时，`approved_amount = 0`，`approved_at` 不为空，`refunded_at` 为空。
  - `refund_status = refunded` 时，`approved_amount` 不为空，`approved_at` 不为空，`refunded_at` 不为空。
  - 同一 `order_item_id` 的累计已审批退款金额不得超过该订单明细实付金额。

### 履约域
本域用于维护学员购买后与班次之间的报名、在读、完成等履约关系。

表说明：

- `student_cohort_rel`：学员班次关系表，记录报名、在读、完成等履约关系。

依赖关系说明：

- `order_item -> student_cohort_rel`：订单明细成交后形成学员与班次的履约关系。
- `student_cohort_rel -> series_cohort`：履约关系挂接具体班次。
- `student_cohort_rel -> student_profile`：履约关系挂接平台级学员档案。

#### `student_cohort_rel`
学员班次关系表，记录报名、在读、完成等履约关系。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `user_id`：下单用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `order_item_id`：订单明细ID，关联 `order_item.id`。
- `enroll_status`：报名状态。枚举值：
  - `active`：在读
  - `completed`：已完成
  - `cancelled`：已取消
  - `refunded`：已退费
- `enroll_at`：报名时间。
- `completed_at`：完成时间。
- `cancelled_at`：取消或退费终止时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_student_cohort_rel_order_item (order_item_id)`
  - `uk_student_cohort_rel_student_cohort (student_id, cohort_id)`
- 外键约束：
  - `fk_student_cohort_rel_institution (institution_id -> org_institution.id)`
  - `fk_student_cohort_rel_user (user_id -> sys_user.id)`
  - `fk_student_cohort_rel_student (student_id -> student_profile.id)`
  - `fk_student_cohort_rel_cohort (cohort_id -> series_cohort.id)`
  - `fk_student_cohort_rel_order_item (order_item_id -> order_item.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= order_item.created_at`
  - `created_at >= series_cohort.created_at`
  - `institution_id` 必须等于 `cohort_id` 对应班次的 `institution_id`。
  - `institution_id` 必须等于 `order_item_id` 对应订单明细的 `institution_id`。
  - `user_id` 必须等于 `order_item_id` 对应订单明细的 `user_id`。
  - `student_id` 必须等于 `order_item_id` 对应订单明细的 `student_id`。
  - `cohort_id` 必须等于 `order_item_id` 对应订单明细的 `cohort_id`。
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `enroll_at >= created_at`
  - `completed_at` 不为空时，`completed_at >= enroll_at`。
  - `cancelled_at` 不为空时，`cancelled_at >= enroll_at`。
  - `completed_at` 与 `cancelled_at` 不能同时有值。
  - `enroll_status = active` 时，`enroll_at` 不为空，`completed_at`、`cancelled_at` 为空。
  - `enroll_status = completed` 时，`enroll_at`、`completed_at` 不为空，`cancelled_at` 为空。
  - `enroll_status = cancelled` 时，`enroll_at`、`cancelled_at` 不为空，`completed_at` 为空。
  - `enroll_status = refunded` 时，`enroll_at`、`cancelled_at` 不为空，`completed_at` 为空。

### 学习域
本域用于维护学员学习过程、考勤、视频观看、作业提交和考试作答等学习行为数据。

表说明：

- `session_attendance`：课次考勤表，记录学员在课次维度的签到与出勤状态。
- `session_video_play`：视频播放会话表，记录学员观看课次视频的播放会话。
- `session_video_play_event`：视频播放事件表，记录播放、暂停、拖动、结束等行为事件。
- `session_homework_submission`：作业提交表，记录学员作业提交、评分和批改状态。
- `session_exam_submission`：考试作答表，记录学员考试作答、成绩和作答状态。

依赖关系说明：

- `student_cohort_rel -> session_attendance`：学员报名班次后产生课次考勤记录。
- `session_video -> session_video_play -> session_video_play_event`：视频播放会话进一步拆分为播放行为事件。
- `session_homework -> session_homework_submission`：课次作业产生学员提交和批改记录。
- `session_exam -> session_exam_submission`：课次考试产生学员作答和成绩记录。

#### `session_attendance`
课次考勤表，记录学员在课次维度的签到、签退与出勤状态。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `session_id`：课次ID，关联 `series_cohort_session.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `user_id`：用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `attendance_status`：考勤状态。枚举值：
  - `pending`：待考勤
  - `present`：出勤
  - `absent`：缺勤
  - `leave`：请假
  - `late`：迟到
- `leave_type`：请假类型。
- `remark`：考勤备注，用于记录请假说明、补签说明或异常考勤原因；正常出勤时可为空。
- `checkin_time`：签到时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_attendance (session_id, student_id)`
- 外键约束：
  - `fk_session_attendance_institution (institution_id -> org_institution.id)`
  - `fk_session_attendance_session (session_id -> series_cohort_session.id)`
  - `fk_session_attendance_cohort (cohort_id -> series_cohort.id)`
  - `fk_session_attendance_user (user_id -> sys_user.id)`
  - `fk_session_attendance_student (student_id -> student_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= series_cohort_session.created_at`
  - `institution_id` 必须等于 `session_id` 对应课次所属机构的 `institution_id`。
  - `institution_id` 必须等于 `cohort_id` 对应班次的 `institution_id`。
  - `cohort_id` 必须等于 `session_id` 对应课次所属班次的 `cohort_id`。
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `student_id` 必须已存在对应 `cohort_id` 的履约关系，且该履约关系状态不能为 `cancelled` 或 `refunded`。
  - `checkin_time` 不为空时，`checkin_time >= created_at`。
  - `attendance_status = pending` 时，`checkin_time` 为空。
  - `attendance_status = present` 时，`checkin_time` 不为空。
  - `attendance_status = leave` 时，`leave_type` 不为空，`checkin_time` 为空。
  - `attendance_status = absent` 时，`checkin_time` 为空。
  - `attendance_status = late` 时，`checkin_time` 不为空。

#### `session_video_play`
视频播放会话表，记录学员观看课次视频的播放会话。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `video_id`：视频资源ID，关联 `session_video.id`。
- `user_id`：用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `play_session_no`：播放会话号。
- `device_type`：设备类型。枚举值：
  - `mobile`：手机
  - `tablet`：平板
  - `desktop`：电脑
- `client_type`：客户端类型。枚举值：
  - `app`：原生 App
  - `h5`：移动网页
  - `pc_web`：PC 网页
  - `mini_program`：小程序
- `device_os`：设备系统。枚举值：
  - `ios`：iOS
  - `android`：Android
  - `windows`：Windows
  - `macos`：macOS
  - `linux`：Linux
  - `harmonyos`：HarmonyOS
  - `unknown`：未知
- `last_position_seconds`：最后播放位置。
- `progress_percent`：观看进度。
- `completed_flag`：是否看完。
- `exit_reason`：退出原因。
- `watched_seconds`：累计观看秒数。
- `started_at`：开始播放时间。
- `ended_at`：结束播放时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_video_play_no (institution_id, play_session_no)`
- 外键约束：
  - `fk_session_video_play_institution (institution_id -> org_institution.id)`
  - `fk_session_video_play_video (video_id -> session_video.id)`
  - `fk_session_video_play_user (user_id -> sys_user.id)`
  - `fk_session_video_play_student (student_id -> student_profile.id)`
- 业务约束：
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= session_video.created_at`
  - `institution_id` 必须等于 `video_id` 对应视频所属机构的 `institution_id`。
  - `student_id` 必须已存在与当前播放行为对应班次的履约关系，且该履约关系状态不能为 `cancelled` 或 `refunded`。
  - `last_position_seconds >= 0`
  - `watched_seconds >= 0`
  - `progress_percent >= 0`
  - `progress_percent <= 100`
  - `last_position_seconds <= video_id` 对应视频的 `duration_seconds`。
  - `started_at >= created_at`
  - `ended_at` 不为空时，`ended_at >= started_at`。
  - `completed_flag = 1` 时，`ended_at` 不为空。
  - `completed_flag = 1` 时，`progress_percent = 100`。
  - `completed_flag = 0` 时，`progress_percent < 100`。

#### `session_video_play_event`
视频播放事件表，记录播放、暂停、拖动、结束等行为事件。

- `id`：主键 ID。
- `play_session_id`：视频播放会话ID，关联 `session_video_play.id`。
- `event_type`：事件类型。枚举值：
  - `play`：开始播放
  - `pause`：暂停播放
  - `resume`：继续播放
  - `seek`：拖动进度
  - `complete`：播放完成
  - `exit`：退出播放
- `position_seconds`：播放位置秒数。
- `playback_rate`：播放倍速。
- `network_type`：网络类型。枚举值：
  - `wifi`：Wi-Fi
  - `mobile_5g`：5G
  - `mobile_4g`：4G
  - `mobile_3g`：3G
  - `ethernet`：有线网络
  - `offline`：离线
  - `unknown`：未知
- `event_payload`：事件扩展信息。
- `event_time`：事件时间。
- `created_at`：创建时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_session_video_play_event_session (play_session_id -> session_video_play.id)`
- 业务约束：
  - `created_at >= session_video_play.created_at`
  - `position_seconds >= 0`
  - `position_seconds <= play_session_id` 对应播放会话视频的 `duration_seconds`。
  - `playback_rate > 0`
  - `event_time >= created_at`
  - `play_session_id` 对应播放会话存在 `started_at` 时，`event_time >= started_at`。
  - `play_session_id` 对应播放会话存在 `ended_at` 时，`event_time <= ended_at`。
  - `event_type = complete` 时，`position_seconds = play_session_id` 对应播放会话视频的 `duration_seconds`。

#### `session_homework_submission`
作业提交表，记录学员作业提交、评分和批改状态。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `homework_id`：作业ID，关联 `session_homework.id`。
- `user_id`：用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `session_id`：所属课次ID，关联 `series_cohort_session.id`。
- `submit_no`：提交编号。
- `submit_status`：提交状态。枚举值：
  - `submitted`：已提交
  - `expired_unsubmitted`：过期未提交
- `total_score`：总分。
- `correction_status`：批改状态。枚举值：
  - `pending`：待批改
  - `corrected`：已批改
- `corrected_by`：批改教师ID，关联 `staff_profile.id`。
- `feedback_text`：教师反馈。
- `submitted_at`：提交时间。
- `corrected_at`：批改时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_homework_submission_no (institution_id, submit_no)`
  - `uk_session_homework_submission_once (homework_id, student_id)`
- 外键约束：
  - `fk_session_homework_submission_institution (institution_id -> org_institution.id)`
  - `fk_session_homework_submission_homework (homework_id -> session_homework.id)`
  - `fk_session_homework_submission_user (user_id -> sys_user.id)`
  - `fk_session_homework_submission_student (student_id -> student_profile.id)`
  - `fk_session_homework_submission_session (session_id -> series_cohort_session.id)`
  - `fk_session_homework_submission_teacher (corrected_by -> staff_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= session_homework.created_at`
  - `created_at >= series_cohort_session.created_at`
  - `institution_id` 必须等于 `homework_id` 对应作业所属机构的 `institution_id`。
  - `institution_id` 必须等于 `session_id` 对应课次所属机构的 `institution_id`。
  - `session_id` 必须等于 `homework_id` 对应作业的 `session_id`。
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `student_id` 必须已存在对应 `session_id` 所属班次的履约关系，且该履约关系状态不能为 `cancelled` 或 `refunded`。
  - `session_id` 对应课次存在作业时，系统必须为该课次所属班次的每个有效学员履约关系生成一条 `session_homework_submission` 记录，保证作业提交表中的学员记录数与该课次对应班次的有效学员数一致。
  - 截止到 `homework_id` 对应作业的 `due_at` 仍未提交作业的学员，系统必须将对应记录状态自动写为 `expired_unsubmitted`，不得缺失记录。
  - `submitted_at` 不为空时，`submitted_at >= created_at`。
  - `corrected_at` 不为空时，`submitted_at` 必须不为空，且 `corrected_at >= submitted_at`。
  - `corrected_by` 不为空时，必须与 `institution_id` 属于同一机构。
  - `corrected_by` 不为空时，`corrected_at` 不为空。
  - `total_score` 不为空时，`total_score >= 0`。
  - `submit_status = submitted` 时，`submitted_at` 不为空。
  - `submit_status = submitted` 时，`submitted_at <= homework_id` 对应作业的 `due_at`。
  - `submit_status = expired_unsubmitted` 时，`submitted_at`、`corrected_at`、`corrected_by`、`total_score` 为空，且当前时间已晚于 `homework_id` 对应作业的 `due_at`。
  - `submit_status = expired_unsubmitted` 时，`correction_status = pending`。
  - `correction_status = pending` 时，`corrected_at`、`corrected_by`、`total_score` 为空。
  - `correction_status = corrected` 时，`corrected_at`、`corrected_by`、`total_score` 不为空，`feedback_text` 可为空。

#### `session_exam_submission`
考试作答表，记录学员考试作答、成绩和作答状态。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `exam_id`：考试ID，关联 `session_exam.id`。
- `user_id`：用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `attempt_no`：作答编号。
- `attempt_status`：作答状态。枚举值：
  - `not_started`：未作答
  - `in_progress`：作答中
  - `submitted`：已提交
  - `absent`：缺考
  - `timeout`：超时交卷
- `duration_seconds`：作答时长。
- `score_value`：得分。
- `start_at`：开始时间。
- `submit_at`：提交时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_session_exam_submission_no (institution_id, attempt_no)`
  - `uk_session_exam_submission_once (exam_id, student_id)`
- 外键约束：
  - `fk_session_exam_submission_institution (institution_id -> org_institution.id)`
  - `fk_session_exam_submission_exam (exam_id -> session_exam.id)`
  - `fk_session_exam_submission_user (user_id -> sys_user.id)`
  - `fk_session_exam_submission_student (student_id -> student_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= session_exam.created_at`
  - `created_at >= sys_user.created_at`
  - `institution_id` 必须等于 `exam_id` 对应考试所属机构的 `institution_id`。
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `student_id` 必须已存在 `exam_id` 对应考试所属班次的履约关系，且该履约关系状态不能为 `cancelled` 或 `refunded`。
  - `exam_id` 对应考试存在时，系统必须为该考试所属班次的每个有效学员履约关系生成一条 `session_exam_submission` 记录，保证考试作答表中的学员记录数与该考试对应班次的有效学员数一致。
  - 截止到 `exam_id` 对应考试的 `deadline_at` 仍未进入考试的学员，系统必须将对应记录状态自动写为 `absent`，不得缺失记录。
  - `start_at` 不为空时，`start_at >= created_at`。
  - `start_at` 不为空时，`start_at >= exam_id` 对应考试的 `window_start_at`。
  - `start_at` 不为空时，`start_at <= exam_id` 对应考试的 `deadline_at`。
  - `submit_at` 不为空时，`start_at` 必须不为空，且 `submit_at >= start_at`。
  - `submit_at` 不为空时，`submit_at <= exam_id` 对应考试的 `deadline_at`。
  - `duration_seconds` 不为空时，`duration_seconds >= 0`。
  - `submit_at` 不为空时，`duration_seconds` 必须不为空，且 `duration_seconds <= exam_id` 对应考试的 `duration_minutes * 60`。
  - `score_value` 不为空时，`0 <= score_value <= exam_id` 对应考试的 `total_score`。
  - `attempt_status = not_started` 时，`start_at`、`submit_at`、`duration_seconds`、`score_value` 为空。
  - `attempt_status = in_progress` 时，`start_at` 不为空，`submit_at`、`score_value` 为空。
  - `attempt_status = submitted` 时，`start_at`、`submit_at`、`duration_seconds` 不为空。
  - `attempt_status = absent` 时，`start_at`、`submit_at`、`duration_seconds`、`score_value` 为空，且当前时间已晚于 `exam_id` 对应考试的 `deadline_at`。
  - `attempt_status = timeout` 时，`start_at`、`submit_at`、`duration_seconds` 不为空，且 `duration_seconds = exam_id` 对应考试的 `duration_minutes * 60`。

### 互动域
本域用于维护班次讨论、回复互动和课程评价等用户互动内容。

表说明：

- `cohort_discussion_topic`：班次讨论主题表，记录讨论主题、置顶状态和关闭状态。
- `cohort_discussion_post`：班次讨论回复表，记录主题回复和回复的回复。
- `cohort_review`：班次评价表，记录学员对班次的打分与评价。

依赖关系说明：

- `series_cohort -> cohort_discussion_topic -> cohort_discussion_post`：班次下产生讨论主题和回复。
- `series_cohort -> cohort_review`：学员可对班次进行评价。

#### `cohort_discussion_topic`
班次讨论主题表，记录讨论主题、置顶状态和关闭状态。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `creator_user_id`：创建人用户ID，关联 `sys_user.id`。
- `topic_title`：主题标题，非空。
- `content_text`：主题内容，非空。
- `is_pinned`：是否置顶。
- `is_closed`：是否关闭。
- `view_count`：浏览数。
- `reply_count`：回复数。
- `last_reply_at`：最后回复时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_cohort_discussion_topic_institution (institution_id -> org_institution.id)`
  - `fk_cohort_discussion_topic_cohort (cohort_id -> series_cohort.id)`
  - `fk_cohort_discussion_topic_creator (creator_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= series_cohort.created_at`
  - `created_at >= sys_user.created_at`
  - `institution_id` 必须等于 `cohort_id` 对应班次的 `institution_id`。
  - `creator_user_id` 必须属于 `institution_id` 对应机构下的有效学员或有效职员。
  - `view_count >= 0`
  - `reply_count >= 0`
  - `reply_count` 固定统计当前主题下 `yn = 1` 的直接回复数量，不统计主题下回复的子回复数量。
  - `last_reply_at` 不为空时，`last_reply_at >= created_at`。
  - 存在 `yn = 1` 的直接回复时，`last_reply_at` 必须等于该主题下最后一条直接回复的 `created_at` 最大值。
  - 不存在 `yn = 1` 的直接回复时，`last_reply_at` 为空。
  - `is_closed = 1` 时，主题不允许再新增回复。
  - `is_pinned = 1` 时，主题必须为有效状态，不能同时为关闭且停用主题。

#### `cohort_discussion_post`
班次讨论回复表，记录主题回复和回复的回复。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `topic_id`：讨论主题ID，关联 `cohort_discussion_topic.id`。
- `parent_post_id`：父回复ID，关联 `cohort_discussion_post.id`。
- `author_user_id`：作者用户ID，关联 `sys_user.id`。
- `content_text`：回复内容，非空。
- `like_count`：点赞数。
- `reply_count`：回复数。
- `yn`：是否启用。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_cohort_discussion_post_institution (institution_id -> org_institution.id)`
  - `fk_cohort_discussion_post_topic (topic_id -> cohort_discussion_topic.id)`
  - `fk_cohort_discussion_post_parent (parent_post_id -> cohort_discussion_post.id)`
  - `fk_cohort_discussion_post_author (author_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= cohort_discussion_topic.created_at`
  - `created_at >= sys_user.created_at`
  - `institution_id` 必须等于 `topic_id` 对应主题的 `institution_id`。
  - `author_user_id` 必须属于 `institution_id` 对应机构下的有效学员或有效职员。
  - `topic_id` 对应主题未关闭时，才允许新增回复。
  - `parent_post_id` 不为空时，父回复必须属于同一 `topic_id`。
  - `parent_post_id` 不为空时，父回复必须为有效状态。
  - `like_count >= 0`
  - `reply_count >= 0`
  - `reply_count` 固定统计当前回复下 `yn = 1` 的直接子回复数量，不递归累计更深层级回复。
  - `yn = 0` 时，该回复视为逻辑失效，不再允许继续挂接子回复。

#### `cohort_review`
班次评价表，记录学员对班次的打分与评价。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `user_id`：用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `review_no`：评价编号。
- `score_overall`：综合评分。
- `score_teacher`：教师评分。
- `score_content`：内容评分。
- `score_service`：服务评分。
- `review_tags`：评价标签，JSON 列表类型。
- `review_content`：评价内容。
- `anonymous_flag`：是否匿名。
- `yn`：是否有效。
- `reviewed_at`：评价时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_cohort_review_no (institution_id, review_no)`
  - `uk_cohort_review_once (cohort_id, student_id)`
- 外键约束：
  - `fk_cohort_review_institution (institution_id -> org_institution.id)`
  - `fk_cohort_review_cohort (cohort_id -> series_cohort.id)`
  - `fk_cohort_review_user (user_id -> sys_user.id)`
  - `fk_cohort_review_student (student_id -> student_profile.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= series_cohort.created_at`
  - `created_at >= sys_user.created_at`
  - `institution_id` 必须等于 `cohort_id` 对应班次的 `institution_id`。
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `student_id` 必须已存在对应 `cohort_id` 的 `student_cohort_rel` 履约关系，且该履约关系状态不能为 `cancelled` 或 `refunded`。
  - `score_overall`、`score_teacher`、`score_content`、`score_service` 必须在 `1` 到 `5` 之间。
  - `reviewed_at >= created_at`
  - `reviewed_at` 不得早于对应 `cohort_id` 的 `start_date`。
  - `review_tags` 可为空；不为空时必须为 JSON 列表类型的标签集合。
  - `review_content` 可为空；不为空时必须为有效评价内容。
  - `anonymous_flag = 1` 时，前台展示必须隐藏用户实名信息，但数据库中仍保留 `user_id` 和 `student_id`。
  - `yn = 0` 时，该评价视为逻辑失效，不参与前台展示和聚合统计。

### 服务域
本域用于维护售后工单、跟进处理和满意度反馈等服务过程数据。

表说明：

- `service_ticket`：客服工单表，记录订单明细级售后问题和处理状态。
- `service_ticket_follow_record`：工单跟进记录表，记录客服处理动作和跟进内容。
- `service_ticket_satisfaction_survey`：工单满意度调查表，记录用户对工单处理结果的满意度反馈。

依赖关系说明：

- `order_item -> service_ticket -> service_ticket_follow_record -> service_ticket_satisfaction_survey`：售后工单记录处理过程和满意度反馈。
- `refund_request -> service_ticket`：退费申请需要客服介入时，可挂接退款类工单记录处理过程。

#### `service_ticket`
客服工单表，记录订单明细级售后问题和处理状态。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `ticket_no`：工单编号。
- `user_id`：用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `order_item_id`：订单明细ID，关联 `order_item.id`。
- `refund_request_id`：退款申请ID，关联 `refund_request.id`。
- `ticket_type`：工单类型。枚举值：
  - `after_sales`：售后咨询
  - `complaint`：投诉反馈
  - `refund`：退费申请
- `ticket_source`：工单来源。枚举值：
  - `user_app`：用户端发起
  - `customer_service`：客服代建
  - `system_auto`：系统自动创建
  - `admin_manual`：后台人工创建
- `priority_level`：优先级。枚举值：
  - `low`：低
  - `medium`：中
  - `high`：高
  - `urgent`：紧急
- `ticket_status`：工单状态。枚举值：
  - `pending`：待处理
  - `in_progress`：处理中
  - `closed`：已关闭
- `assignee_user_id`：处理人用户ID，关联 `sys_user.id`。
- `title`：工单标题，非空。
- `ticket_content`：工单内容，非空。
- `yn`：是否有效。
- `first_response_at`：首次响应时间。
- `closed_at`：关闭时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_service_ticket_no (institution_id, ticket_no)`
- 外键约束：
  - `fk_service_ticket_institution (institution_id -> org_institution.id)`
  - `fk_service_ticket_user (user_id -> sys_user.id)`
  - `fk_service_ticket_student (student_id -> student_profile.id)`
  - `fk_service_ticket_order_item (order_item_id -> order_item.id)`
  - `fk_service_ticket_refund_request (refund_request_id -> refund_request.id)`
  - `fk_service_ticket_assignee (assignee_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= order_item.created_at`
  - `institution_id` 必须等于 `order_item_id` 对应订单明细的 `institution_id`。
  - `user_id` 必须等于 `order_item_id` 对应订单明细所属订单的 `user_id`。
  - `student_id` 必须等于 `order_item_id` 对应订单明细的 `student_id`。
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `refund_request_id` 不为空时，必须属于 `order_item_id` 和 `user_id`。
  - `assignee_user_id` 不为空时，必须属于 `institution_id` 对应机构下的有效职员。
  - `first_response_at` 不为空时，`first_response_at >= created_at`。
  - `closed_at` 不为空时，`closed_at >= created_at`。
  - `closed_at` 不为空时，`first_response_at` 可为空或满足 `closed_at >= first_response_at`。
  - `ticket_status = pending` 时，`closed_at` 为空。
  - `ticket_status = in_progress` 时，`first_response_at` 不为空，`closed_at` 为空。
  - `ticket_status = closed` 时，`closed_at` 不为空。
  - `ticket_type = refund` 时，`refund_request_id` 不为空，且 `order_item_id` 对应订单明细必须存在可退费场景。
  - `ticket_type != refund` 时，`refund_request_id` 为空。
  - `yn = 0` 时，该工单视为逻辑失效，不参与前台展示和待处理统计。

#### `service_ticket_follow_record`
工单跟进记录表，记录客服处理动作和跟进内容。

- `id`：主键 ID。
- `ticket_id`：服务工单ID，关联 `service_ticket.id`。
- `follow_user_id`：跟进人用户ID，关联 `sys_user.id`。
- `follow_type`：跟进类型。枚举值：
  - `reply_user`：回复用户
  - `status_update`：状态更新
  - `refund_review`：退费审核
  - `internal_note`：内部备注
  - `escalation`：升级处理
- `follow_channel`：跟进渠道。枚举值：
  - `phone`：电话
  - `user_app`：用户端消息
  - `sms`：短信
  - `wechat`：微信
  - `internal_system`：内部系统
  - `offline`：线下沟通
- `follow_result`：跟进结果。枚举值：
  - `pending_follow_up`：待继续跟进
  - `user_confirmed`：用户已确认
  - `user_unreachable`：用户未联系上
  - `resolved`：问题已解决
  - `escalated`：已升级处理
- `follow_content`：跟进内容，非空。
- `followed_at`：跟进时间，非空。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_service_ticket_follow_record_ticket (ticket_id -> service_ticket.id)`
  - `fk_service_ticket_follow_record_user (follow_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= service_ticket.created_at`
  - `follow_user_id` 必须属于 `ticket_id` 对应工单所属机构下的有效职员。
  - `followed_at >= created_at`
  - `ticket_id` 对应工单状态为 `closed` 时，`followed_at` 不得晚于工单 `closed_at`。
  - `follow_type = refund_review` 时，`ticket_id` 对应工单的 `ticket_type` 必须为 `refund`。
  - `follow_result = resolved` 时，`ticket_id` 对应工单状态应为 `closed` 或后续被更新为 `closed`。

#### `service_ticket_satisfaction_survey`
工单满意度调查表，记录用户对工单处理结果的满意度反馈。

- `id`：主键 ID。
- `survey_no`：满意度编号。
- `user_id`：用户ID，关联 `sys_user.id`。
- `student_id`：学员档案ID，关联 `student_profile.id`。
- `ticket_id`：服务工单ID，关联 `service_ticket.id`。
- `score_value`：满意度评分。
- `comment_text`：反馈内容。
- `yn`：是否有效。
- `surveyed_at`：评价时间，非空。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_service_ticket_satisfaction_survey_no (survey_no)`
  - `uk_service_ticket_satisfaction_survey_ticket (ticket_id)`
- 外键约束：
  - `fk_service_ticket_satisfaction_survey_user (user_id -> sys_user.id)`
  - `fk_service_ticket_satisfaction_survey_student (student_id -> student_profile.id)`
  - `fk_service_ticket_satisfaction_survey_ticket (ticket_id -> service_ticket.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= service_ticket.created_at`
  - `surveyed_at >= created_at`
  - `student_id` 对应学员档案必须属于 `user_id`。
  - `user_id` 必须等于 `ticket_id` 对应工单的 `user_id`。
  - `student_id` 必须等于 `ticket_id` 对应工单的 `student_id`。
  - `ticket_id` 对应工单状态必须为 `closed`。
  - `surveyed_at >= ticket_id` 对应工单的 `closed_at`。
  - `score_value` 不为空时，`1 <= score_value <= 5`。
  - `yn = 0` 时，该满意度记录视为逻辑失效，不参与前台展示和满意度统计。

### 经营衍生域
本域用于维护课酬结算、渠道返佣、风险预警和内容审核等经营衍生数据。

表说明：

- `teacher_compensation_bill`：教师课酬账单表，记录教师课酬结算单头。
- `teacher_compensation_item`：教师课酬明细表，记录单个课次或课酬项目的结算金额。
- `channel_commission_bill`：渠道返佣账单表，记录渠道返佣单头和汇总金额。
- `channel_commission_item`：渠道返佣明细表，记录单笔订单的返佣金额。
- `risk_alert_event`：风险预警事件表，记录异常退款、异常学习、异常操作等识别结果。
- `risk_disposal_record`：风险处置记录表，记录预警事件的人工处理过程。
- `ugc_moderation_task`：内容审核任务表，记录讨论、评价、评论等 UGC 内容的审核任务。

依赖关系说明：

- `teacher_compensation_bill -> teacher_compensation_item`：课酬账单下记录课次或课酬项目明细。
- `channel_commission_bill -> channel_commission_item`：渠道返佣账单下记录订单级返佣明细。
- `risk_alert_event -> risk_disposal_record`：风险预警事件产生后记录人工处置过程。
- `ugc_moderation_task` 关联讨论主题或讨论回复，用于记录 UGC 审核流程。

#### `teacher_compensation_bill`
教师课酬账单表，记录教师课酬结算单头。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `bill_no`：课酬单编号。
- `teacher_id`：教师档案ID，关联 `staff_profile.id`。
- `settle_period`：结算周期。
- `bill_status`：课酬单状态。枚举值：
  - `pending`：待审批
  - `approved`：已审批
  - `paid`：已打款
- `lesson_count`：结算课次数。
- `base_amount`：基础课酬金额。
- `bonus_amount`：奖励金额。
- `deduction_amount`：扣减金额。
- `payable_amount`：应付金额。
- `approver_user_id`：审批人用户ID，关联 `sys_user.id`。
- `yn`：是否有效。
- `settled_at`：结算时间。
- `paid_at`：支付时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_teacher_compensation_bill_no (institution_id, bill_no)`
- 外键约束：
  - `fk_teacher_compensation_bill_institution (institution_id -> org_institution.id)`
  - `fk_teacher_compensation_bill_teacher (teacher_id -> staff_profile.id)`
  - `fk_teacher_compensation_bill_approver (approver_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `created_at >= staff_profile.created_at`
  - `teacher_id` 对应职员档案必须属于 `institution_id` 对应机构。
  - `teacher_id` 对应职员档案的角色类别必须为教师类岗位。
  - `lesson_count >= 0`
  - `base_amount >= 0`
  - `bonus_amount >= 0`
  - `deduction_amount >= 0`
  - `payable_amount = base_amount + bonus_amount - deduction_amount`
  - `payable_amount >= 0`
  - `approver_user_id` 不为空时，必须属于 `institution_id` 对应机构下的有效职员。
  - `settled_at` 不为空时，`settled_at >= created_at`。
  - `paid_at` 不为空时，`settled_at` 必须不为空，且 `paid_at >= settled_at`。
  - `bill_status = pending` 时，`approver_user_id`、`settled_at`、`paid_at` 为空。
  - `bill_status = approved` 时，`approver_user_id`、`settled_at` 不为空，`paid_at` 为空。
  - `bill_status = paid` 时，`approver_user_id`、`settled_at`、`paid_at` 不为空。
  - `yn = 0` 时，该课酬单视为逻辑失效，不参与结算展示和统计。

#### `teacher_compensation_item`
教师课酬明细表，记录单个课次或课酬项目的结算金额。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `bill_id`：教师课酬单ID，关联 `teacher_compensation_bill.id`。
- `teacher_id`：教师档案ID，关联 `staff_profile.id`。
- `cohort_id`：班次ID，关联 `series_cohort.id`。
- `session_id`：课次ID，关联 `series_cohort_session.id`。
- `item_type`：明细类型。枚举值：
  - `session_fee`：课次课酬
  - `bonus`：奖励项
  - `deduction`：扣减项
  - `adjustment`：人工调整项
- `unit_price`：单价。
- `item_amount`：明细金额。
- `remark`：课酬明细备注，用于记录奖励、扣减、人工调整等补充说明；标准课次课酬明细通常为空。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_teacher_compensation_item_session_fee (bill_id, session_id)`：仅用于 `item_type = session_fee` 的课次课酬明细
- 外键约束：
  - `fk_teacher_compensation_item_institution (institution_id -> org_institution.id)`
  - `fk_teacher_compensation_item_bill (bill_id -> teacher_compensation_bill.id)`
  - `fk_teacher_compensation_item_teacher (teacher_id -> staff_profile.id)`
  - `fk_teacher_compensation_item_cohort (cohort_id -> series_cohort.id)`
  - `fk_teacher_compensation_item_session (session_id -> series_cohort_session.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= teacher_compensation_bill.created_at`
  - `institution_id` 必须等于 `bill_id` 对应课酬单的 `institution_id`。
  - `teacher_id` 必须等于 `bill_id` 对应课酬单的 `teacher_id`。
  - `teacher_id` 对应职员档案必须属于 `institution_id` 对应机构。
  - `cohort_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `session_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `session_id` 不为空时，`cohort_id` 必须不为空，且 `session_id` 对应课次必须属于 `cohort_id`。
  - `item_type = session_fee` 时，同一课酬单下同一课次只允许存在一条课次课酬明细。
  - `item_type = session_fee` 时，`session_id`、`cohort_id`、`unit_price` 不为空，且 `item_amount = unit_price`。
  - `item_type = bonus` 时，`item_amount > 0`。
  - `item_type = deduction` 时，`item_amount < 0`。
  - `item_type = adjustment` 时，`item_amount != 0`。
  - `item_type != session_fee` 时，`session_id` 可为空。
  - `unit_price` 不为空时，`unit_price >= 0`。
  - 同一课酬单下所有明细 `item_amount` 汇总值必须等于 `bill_id` 对应课酬单的 `payable_amount`。

#### `channel_commission_bill`
渠道返佣账单表，记录渠道返佣单头和汇总金额。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `bill_no`：返佣单编号。
- `channel_id`：渠道ID，关联 `dim_channel.id`。
- `settle_period`：结算周期。
- `bill_status`：返佣单状态。枚举值：
  - `pending`：待审批
  - `approved`：已审批
  - `paid`：已打款
- `order_count`：关联订单数。
- `commission_amount`：返佣金额。
- `approver_user_id`：审批人用户ID，关联 `sys_user.id`。
- `yn`：是否有效。
- `settled_at`：结算时间。
- `paid_at`：支付时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_channel_commission_bill_no (institution_id, bill_no)`
- 外键约束：
  - `fk_channel_commission_bill_institution (institution_id -> org_institution.id)`
  - `fk_channel_commission_bill_channel (channel_id -> dim_channel.id)`
  - `fk_channel_commission_bill_approver (approver_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `channel_id` 对应渠道必须为机构招生渠道。
  - `order_count >= 0`
  - `commission_amount >= 0`
  - `approver_user_id` 不为空时，必须属于 `institution_id` 对应机构下的有效职员。
  - `settled_at` 不为空时，`settled_at >= created_at`。
  - `paid_at` 不为空时，`settled_at` 必须不为空，且 `paid_at >= settled_at`。
  - `bill_status = pending` 时，`approver_user_id`、`settled_at`、`paid_at` 为空。
  - `bill_status = approved` 时，`approver_user_id`、`settled_at` 不为空，`paid_at` 为空。
  - `bill_status = paid` 时，`approver_user_id`、`settled_at`、`paid_at` 不为空。
  - 同一返佣单下明细记录数必须等于 `order_count`。
  - 同一返佣单下所有明细 `commission_amount` 汇总值必须等于 `commission_amount`。
  - `yn = 0` 时，该返佣单视为逻辑失效，不参与返佣展示和统计。

#### `channel_commission_item`
渠道返佣明细表，记录单笔订单的返佣金额。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `bill_id`：渠道返佣单ID，关联 `channel_commission_bill.id`。
- `order_item_id`：订单明细ID，关联 `order_item.id`。
- `commission_rate`：返佣比例，按 `0` 到 `1` 之间的小数存储，例如 `0.15` 表示 `15%`。
- `base_amount`：返佣基数。
- `commission_amount`：返佣金额。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_channel_commission_item_order_item (bill_id, order_item_id)`
- 外键约束：
  - `fk_channel_commission_item_institution (institution_id -> org_institution.id)`
  - `fk_channel_commission_item_bill (bill_id -> channel_commission_bill.id)`
  - `fk_channel_commission_item_order_item (order_item_id -> order_item.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= channel_commission_bill.created_at`
  - `created_at >= order_item.created_at`
  - `institution_id` 必须等于 `bill_id` 对应返佣单的 `institution_id`。
  - `order_item_id` 对应订单明细必须属于 `institution_id` 对应机构。
  - `order_item_id` 对应订单的 `order_source_channel_id` 必须等于 `bill_id` 对应返佣单的 `channel_id`。
  - `0 <= commission_rate <= 1`
  - `base_amount >= 0`
  - `commission_amount >= 0`
  - `commission_amount = ROUND(base_amount * commission_rate, 2)`

#### `risk_alert_event`
风险预警事件表，记录异常退款、异常学习、异常操作等识别结果。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `alert_no`：预警编号。
- `alert_type`：预警类型。枚举值：
  - `refund_anomaly`：退款异常
  - `learning_anomaly`：学习异常
  - `exam_anomaly`：考试异常
  - `ugc_anomaly`：内容异常
  - `operation_anomaly`：操作异常
- `risk_level`：风险等级。枚举值：
  - `low`：低风险
  - `medium`：中风险
  - `high`：高风险
  - `critical`：高危
- `related_user_id`：关联用户ID，关联 `sys_user.id`。
- `related_student_id`：关联学员档案ID，关联 `student_profile.id`。
- `cohort_id`：关联班次ID，关联 `series_cohort.id`。
- `session_id`：关联课次ID，关联 `series_cohort_session.id`。
- `order_item_id`：关联订单明细ID，关联 `order_item.id`。
- `refund_request_id`：关联退款申请ID，关联 `refund_request.id`。
- `related_exam_attempt_id`：关联考试作答ID，关联 `session_exam_submission.id`。
- `ugc_content_type`：UGC 内容类型。枚举值：
  - `topic`：讨论主题
  - `post`：讨论回复
  - `review`：班次评价
- `ugc_content_id`：UGC 内容ID，按 `ugc_content_type` 指向对应内容主键。
- `alert_source`：预警来源。枚举值：
  - `rule_engine`：规则引擎
  - `manual_report`：人工上报
  - `model_detection`：模型识别
  - `scheduled_job`：定时任务
- `alert_reason`：预警原因，非空。
- `event_payload`：事件详情。
- `alert_status`：预警状态。枚举值：
  - `pending`：待处理
  - `in_progress`：处理中
  - `closed`：已关闭
- `yn`：是否有效。
- `detected_at`：识别时间。
- `closed_at`：关闭时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_risk_alert_event_no (institution_id, alert_no)`
- 外键约束：
  - `fk_risk_alert_event_institution (institution_id -> org_institution.id)`
  - `fk_risk_alert_event_user (related_user_id -> sys_user.id)`
  - `fk_risk_alert_event_student (related_student_id -> student_profile.id)`
  - `fk_risk_alert_event_cohort (cohort_id -> series_cohort.id)`
  - `fk_risk_alert_event_session (session_id -> series_cohort_session.id)`
  - `fk_risk_alert_event_order_item (order_item_id -> order_item.id)`
  - `fk_risk_alert_event_refund_request (refund_request_id -> refund_request.id)`
  - `fk_risk_alert_event_exam_attempt (related_exam_attempt_id -> session_exam_submission.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `detected_at >= created_at`
  - `closed_at` 不为空时，`closed_at >= detected_at`。
  - `related_student_id` 不为空时，必须属于 `related_user_id`。
  - `cohort_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `session_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `session_id` 不为空时，`cohort_id` 必须不为空，且 `session_id` 对应课次必须属于 `cohort_id`。
  - `order_item_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `refund_request_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `refund_request_id` 不为空时，`order_item_id` 必须不为空，且 `refund_request_id` 对应退款申请必须属于 `order_item_id`。
  - `related_exam_attempt_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `alert_type = refund_anomaly` 时，`refund_request_id`、`order_item_id` 不为空。
  - `alert_type = refund_anomaly` 时，`related_exam_attempt_id`、`ugc_content_type`、`ugc_content_id` 为空。
  - `alert_type = learning_anomaly` 时，`cohort_id` 或 `session_id` 至少一个不为空。
  - `alert_type = exam_anomaly` 时，`related_exam_attempt_id` 不为空。
  - `alert_type = exam_anomaly` 时，`refund_request_id`、`ugc_content_type`、`ugc_content_id` 为空。
  - `alert_type = ugc_anomaly` 时，`ugc_content_type`、`ugc_content_id` 不为空。
  - `alert_type = ugc_anomaly` 时，`refund_request_id`、`order_item_id`、`related_exam_attempt_id` 为空。
  - `alert_type = operation_anomaly` 时，`related_user_id` 不为空。
  - `alert_type != ugc_anomaly` 时，`ugc_content_type`、`ugc_content_id` 为空。
  - `ugc_content_type = topic` 时，`ugc_content_id` 必须等于某条 `cohort_discussion_topic.id`，且该内容属于 `institution_id` 对应机构。
  - `ugc_content_type = post` 时，`ugc_content_id` 必须等于某条 `cohort_discussion_post.id`，且该内容属于 `institution_id` 对应机构。
  - `ugc_content_type = review` 时，`ugc_content_id` 必须等于某条 `cohort_review.id`，且该内容属于 `institution_id` 对应机构。
  - `alert_status = pending` 时，`closed_at` 为空。
  - `alert_status = in_progress` 时，`closed_at` 为空。
  - `alert_status = closed` 时，`closed_at` 不为空。
  - `yn = 0` 时，该预警记录视为逻辑失效，不参与待处理统计。

#### `risk_disposal_record`
风险处置记录表，记录预警事件的人工处理过程。

- `id`：主键 ID。
- `alert_id`：风险预警事件ID，关联 `risk_alert_event.id`。
- `handler_user_id`：处理人用户ID，关联 `sys_user.id`。
- `action_type`：处置动作类型。枚举值：
  - `review`：人工复核
  - `contact_user`：联系用户
  - `freeze_account`：冻结账号
  - `mark_false_positive`：标记误报
  - `close_alert`：关闭预警
- `action_result`：处置结果。枚举值：
  - `pending_follow_up`：待继续跟进
  - `confirmed_risk`：确认风险
  - `false_positive`：确认误报
  - `resolved`：已解决
- `action_note`：处置说明。
- `handled_at`：处置时间，非空。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - 无
- 外键约束：
  - `fk_risk_disposal_record_alert (alert_id -> risk_alert_event.id)`
  - `fk_risk_disposal_record_handler (handler_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= risk_alert_event.created_at`
  - `handled_at >= created_at`
  - `handler_user_id` 必须属于 `alert_id` 对应预警所属机构下的有效职员。
  - `alert_id` 对应预警关闭后，`handled_at` 不得晚于其 `closed_at`。
  - `action_result = resolved` 时，`alert_id` 对应预警状态应为 `closed` 或后续被更新为 `closed`。
  - `action_result = false_positive` 时，`action_type` 必须为 `mark_false_positive`。

#### `ugc_moderation_task`
内容审核任务表，记录讨论、评价、评论等 UGC 内容的审核任务。

- `id`：主键 ID。
- `institution_id`：机构ID，关联 `org_institution.id`。
- `task_no`：审核任务编号。
- `content_type`：内容类型。枚举值：
  - `topic`：讨论主题
  - `post`：讨论回复
  - `review`：班次评价
- `topic_id`：讨论主题ID，关联 `cohort_discussion_topic.id`。
- `post_id`：讨论回复ID，关联 `cohort_discussion_post.id`。
- `review_id`：班次评价ID，关联 `cohort_review.id`。
- `submit_user_id`：提交用户ID，关联 `sys_user.id`。
- `moderator_user_id`：审核人用户ID，关联 `sys_user.id`。
- `moderation_status`：审核状态。枚举值：
  - `pending`：待审核
  - `approved`：已通过
  - `rejected`：已驳回
- `risk_level`：风险等级。枚举值：
  - `low`：低风险
  - `medium`：中风险
  - `high`：高风险
- `reject_reason`：驳回原因。
- `yn`：是否有效。
- `submitted_at`：提交时间，非空。
- `moderated_at`：审核时间。
- `created_at`：创建时间。
- `updated_at`：更新时间。

- 唯一性约束：
  - `uk_ugc_moderation_task_no (institution_id, task_no)`
- 外键约束：
  - `fk_ugc_moderation_task_institution (institution_id -> org_institution.id)`
  - `fk_ugc_moderation_task_topic (topic_id -> cohort_discussion_topic.id)`
  - `fk_ugc_moderation_task_post (post_id -> cohort_discussion_post.id)`
  - `fk_ugc_moderation_task_review (review_id -> cohort_review.id)`
  - `fk_ugc_moderation_task_submit_user (submit_user_id -> sys_user.id)`
  - `fk_ugc_moderation_task_moderator (moderator_user_id -> sys_user.id)`
- 业务约束：
  - `updated_at >= created_at`
  - `created_at >= org_institution.created_at`
  - `submitted_at >= created_at`
  - `moderated_at` 不为空时，`moderated_at >= submitted_at`。
  - `content_type = topic` 时，`topic_id` 不为空，`post_id` 为空。
  - `content_type = post` 时，`post_id` 不为空。
  - `content_type = post` 时，`topic_id` 不为空，且 `post_id` 对应回复必须属于 `topic_id`。
  - `content_type = topic` 时，`review_id` 为空。
  - `content_type = post` 时，`review_id` 为空。
  - `content_type = review` 时，`review_id` 不为空，`topic_id`、`post_id` 为空。
  - `topic_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `post_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `review_id` 不为空时，必须属于 `institution_id` 对应机构。
  - `submit_user_id` 必须等于待审核内容的提交用户。
  - `moderator_user_id` 不为空时，必须属于 `institution_id` 对应机构下的有效职员。
  - `moderation_status = pending` 时，`moderator_user_id`、`moderated_at`、`reject_reason` 为空。
  - `moderation_status = approved` 时，`moderator_user_id`、`moderated_at` 不为空，`reject_reason` 为空。
  - `moderation_status = rejected` 时，`moderator_user_id`、`moderated_at`、`reject_reason` 不为空。
  - `yn = 0` 时，该审核任务视为逻辑失效，不参与待审核统计。

## 数据生成
### 生成原则
- 分层顺序固定为 `Layer1 -> Layer2 -> Layer3 -> Layer4 -> Layer5 -> Layer6 -> Layer7`，后层只能依赖前层已落库数据。
- 基础维度和组织主数据优先保证“稳定可回放”，优先从 `seeds` 导入或按固定枚举生成，不在不同批次之间漂移编码口径。
- 所有编码类字段统一使用稳定规则生成，例如 `INS000001`、`SER000001`、`COH000001`、`ORD0000000001`、`PAY0000000001`，保证重复跑批时便于排查。
- 时间字段统一遵循“主表先、子表后；创建时间先、更新时间后；业务发生时间不早于创建时间”的原则，保证外键和业务约束同时成立。
- 交易与履约链路统一从课程供给快照反推，不生成无法报名、无法支付、无法退费或无法学习的孤立数据。
- 学习、互动、服务、经营衍生数据必须建立在真实履约关系之上，不允许脱离 `student_cohort_rel` 独立生成。

### 时间跨度口径
- 时间基准：以脚本运行环境的本地时间为准，取执行当天当前日期为基准日 `T`，不使用数据库服务器时间作为生成基准。
- 种子维度表：如果字段直接来自 `seeds`，则保持种子中的业务编码、排序号和基础时间口径；程序只补齐目标格式，不改写业务含义。
- 组织与账号域：`sys_user`、`org_institution`、`org_campus`、`org_department`、`org_staff_role`、`staff_profile`、`student_profile` 的创建时间统一覆盖 `T-1460` 到 `T-180`。
- 课程供给域：`series` 的创建时间覆盖 `T-730` 到 `T`；`series_cohort`、`series_cohort_course`、`series_cohort_session`、`session_homework`、`session_exam` 的创建时间统一覆盖 `T-730` 到 `T+90`，支持历史班次、当前班次和未来班次共存。
- 后续业务域：转化、交易、履约、学习、互动、服务、经营衍生等数据不单独设定统一时间窗口，只要求时间关系能够与前序主数据、主链路事件和依赖记录自然衔接。
- 时序约束：后续业务数据仍须满足“先有课程供给，再有转化交易，再有履约学习，再有互动服务和经营衍生”的因果顺序；未来班次不应提前生成真实学习行为，经营衍生数据也必须由前序业务行为反推生成，不独立凭空造数。

### 集成执行说明
以下内容按实际执行顺序组织。每个阶段都同时包含：

- 本阶段处理哪些表
- 这些表如何生成
- 具体执行步骤
- 本阶段完成后的检查点

### 阶段 1：Layer1 基础维度与组织主数据
- 目标：导入基础维度，生成机构、校区、部门、职员角色和平台账号，为课程、交易和学习行为提供稳定引用。
- 处理表：`dim_channel`、`dim_course_category`、`dim_question_type`、`dim_learner_identity`、`dim_grade`、`dim_education_level`、`dim_learning_goal`、`sys_user`、`org_institution`、`org_campus`、`org_department`、`org_staff_role`、`staff_profile`、`org_institution_manager`、`org_campus_manager`、`org_department_manager`、`org_classroom`、`student_profile`

表级说明：

- `dim_channel`
  - 来源：导入 `seeds/1_foundation/dim_channel.csv`。
  - 生成方式：按渠道类别和渠道编码导入机构招生渠道平铺记录。
  - 关键约束：`(channel_category_code, channel_code)` 唯一。
- `dim_course_category`
  - 来源：导入 `seeds/1_foundation/dim_course_category.csv`。
  - 生成方式：先导入顶级分类，再按 `parent_category_code` 解析父级分类并建立分类树。
  - 关键约束：`category_code` 唯一；非顶级分类必须能找到父级分类。
- `dim_question_type`
  - 来源：导入 `seeds/1_foundation/dim_question_type.csv`。
  - 生成方式：导入题型编码、题型名称、客观题标记和自动判分标记。
  - 关键约束：`type_code` 唯一；客观题和自动判分标记口径一致。
- `dim_learner_identity`
  - 来源：导入 `seeds/1_foundation/dim_learner_identity.csv`。
  - 生成方式：导入在校生、职场人、求职者、自由职业者等学习者身份。
  - 关键约束：`identity_code` 唯一。
- `dim_grade`
  - 来源：导入 `seeds/1_foundation/dim_grade.csv`。
  - 生成方式：先导入学段节点，再按 `parent_grade_code` 解析年级节点并建立学业层级树。
  - 关键约束：`grade_code` 唯一；`grade_type = stage` 时无父级，`grade_type = grade` 时必须有父级学段。
- `dim_education_level`
  - 来源：导入 `seeds/1_foundation/dim_education_level.csv`。
  - 生成方式：导入最高学历层次编码和名称。
  - 关键约束：`level_code` 唯一。
- `dim_learning_goal`
  - 来源：导入 `seeds/1_foundation/dim_learning_goal.csv`。
  - 生成方式：导入提分、升学、考证、就业、兴趣等学习目标。
  - 关键约束：`goal_code` 唯一。
- `sys_user`
  - 来源：程序生成。
  - 生成方式：覆盖职员账号和学员账号，注册时必须选择职员或学员身份。
  - 关键约束：手机号、邮箱唯一；生日早于账号创建时间；每个账号必须对应 `staff_profile` 或 `student_profile` 之一。
- `org_institution`
  - 来源：导入 `seeds/1_foundation/org_institution.csv`。
  - 生成方式：导入机构编码、机构类型、名称和地址信息。
  - 关键约束：`institution_code` 唯一；`updated_at >= created_at`。
- `org_campus`
  - 来源：导入 `seeds/1_foundation/org_campus.csv`。
  - 生成方式：按 `institution_code` 解析机构后导入校区。
  - 关键约束：同一机构下 `campus_code` 唯一；校区创建时间不早于机构创建时间。
- `org_department`
  - 来源：导入 `seeds/1_foundation/org_department.csv`。
  - 生成方式：按 `institution_code` 和 `campus_code` 解析组织归属后导入校区级部门。
  - 关键约束：同一机构下 `dept_code` 唯一；部门创建时间不早于所属机构和校区。
- `org_staff_role`
  - 来源：程序生成。
  - 生成方式：为每个机构生成自定义职员角色体系，覆盖教师、教务、销售、运营、服务和管理类角色。
  - 关键约束：同一机构下 `role_code` 唯一；角色归属机构必须存在。
- `staff_profile`
  - 来源：程序生成。
  - 生成方式：为职员账号生成机构内唯一职员档案，同一账号允许在不同机构存在多条职员档案。
  - 关键约束：`(institution_id, user_id)` 唯一；`staff_role_id` 必须与机构一致。
- `org_institution_manager`
  - 来源：程序生成。
  - 生成方式：从机构管理类或教务类职员中为每个机构挑选当前负责人。
  - 关键约束：每个机构最多一条负责人关系；负责人职员必须属于该机构。
- `org_campus_manager`
  - 来源：程序生成。
  - 生成方式：从校区所属职员中为每个校区挑选当前负责人。
  - 关键约束：每个校区最多一条负责人关系；负责人职员的机构和校区必须与校区一致。
- `org_department_manager`
  - 来源：程序生成。
  - 生成方式：从部门所属职员中为每个部门挑选当前负责人。
  - 关键约束：每个部门最多一条负责人关系；负责人职员必须与部门归属机构和校区一致。
- `org_classroom`
  - 来源：程序生成。
  - 生成方式：按机构和校区生成线下教室，并按机构生成直播间资源。
  - 关键约束：线下教室必须关联校区；直播间可不关联校区；同一机构下 `room_code` 唯一。
- `student_profile`
  - 来源：程序生成。
  - 生成方式：为未生成职员档案的账号生成平台级唯一学员档案，多个机构共享。
  - 关键约束：`user_id` 唯一；所有非职员账号必须生成学员档案；在校生填 `grade_id`，非在校生填 `education_level_id`。

Checklist：

- [x] 导入全部基础维度表。
- [x] 生成机构、校区、部门和职员角色体系。
- [x] 生成平台账号、职员档案和学员档案。
- [x] 生成机构、校区、部门负责人关系。
- [x] 生成教室和直播间资源。
- [x] 执行 Layer1 层级校验、唯一性校验和组织归属校验。

### 阶段 2：Layer2 课程供给主数据
- 目标：生成课程系列、班次、课次、教师安排、教学资源、作业和考试等教务主数据。
- 处理表：`series`、`series_category_rel`、`series_cohort`、`series_cohort_course`、`series_cohort_session`、`session_teacher_rel`、`session_asset`、`session_video`、`session_video_chapter`、`session_homework`、`session_exam`

表级说明：

- `series`
  - 来源：导入 `seeds/2_course/series.csv` 作为课程系列模板。
  - 生成方式：围绕机构、课程分类、适用学员身份、学习目标和学业层级展开生成课程产品 SPU。
  - 关键约束：`delivery_mode`、适用目标和分类关系一致；售卖状态与发布时间口径一致。
- `series_cohort`
  - 来源：程序生成。
  - 生成方式：每个课程系列生成历史、当前、未来多个班次；线下班次挂接校区并按开班/结班周期生成，直播班次不挂接校区但仍按开班/结班周期生成，录播班次不挂接校区且不设置结班日期。
  - 关键约束：班主任必须属于同机构且职员角色为教务类；仅线下班次要求班主任与班次校区一致。
- `series_cohort_course` / `series_cohort_session`
  - 来源：`series_cohort_course` 导入 `seeds/2_course/series_course.csv` 中的课程模块模板，`series_cohort_session` 由程序生成。
  - 生成方式：先按班次匹配课程系列对应的模块模板生成 `series_cohort_course`，再按模块课次数展开生成 `series_cohort_session`，保证日期落在班次范围内。
  - 关键约束：课次时间窗、教室类型与授课方式匹配。
- `session_teacher_rel`
  - 来源：程序生成。
  - 生成方式：为课次生成主讲教师或助教关系。
  - 关键约束：教师必须属于同机构且角色类别为教师类。
- `session_asset` / `session_video` / `session_video_chapter`
  - 来源：程序生成。
  - 生成方式：按课次生成讲义、练习、图片、视频资源；视频再拆章节。
  - 关键约束：视频资源必须来自 `material_category = video` 的课次资源，章节时间区间不能越界。
- `session_homework` / `session_exam`
  - 来源：程序生成。
  - 生成方式：仅对有学习目标的课次生成作业和考试；考试窗口长度必须覆盖考试时长。
  - 关键约束：发布时间、起止窗口和创建人归属正确。

Checklist：

- [x] 生成课程系列及分类映射。
- [x] 生成班次、班次课程模块和课次。
- [x] 生成课次教师关系与教学资源。
- [x] 生成课次视频及视频章节。
- [x] 生成作业与考试。
- [x] 执行 Layer2 时间顺序、组织归属、授课方式与资源类型匹配校验。

### 阶段 3：Layer3 题库、营销与转化准备
- 目标：补齐题库、题目、优惠券、咨询、领券、曝光、访问、搜索、收藏和购物车等转化前数据。
- 处理表：`question_bank`、`question`、`session_homework_question_rel`、`session_exam_question_rel`、`coupon`、`coupon_category_rel`、`coupon_series_rel`、`series_exposure_log`、`series_visit_log`、`series_search_log`、`series_favorite`、`shopping_cart_item`、`consultation_record`、`coupon_receive_record`

表级说明：

- 题库组
  - 来源：导入 `seeds/3_question/question_bank.csv` 和 `seeds/3_question/question.csv` 作为题库与题目模板。
  - 生成方式：按机构和课程分类展开题库与题目，再挂接到作业/考试。
  - 关键约束：题库、题目、题型和课程分类闭环成立。
- 优惠券组
  - 来源：程序生成。
  - 生成方式：生成平台券与机构券模板，再生成分类适用范围、课程适用范围和用户领券记录。
  - 默认规则：生成的优惠券模板统一写入 `per_user_limit = 1`。
  - 关键约束：金额型券与折扣型券字段规则正确，领券状态与时间口径一致，同一用户对同一券模板最多生成 1 条领券记录。
- 转化行为组
  - 来源：程序生成。
  - 生成方式：按课程系列生成曝光、访问、搜索、收藏、加购和咨询行为样本。
  - 关键约束：访问必须能追溯曝光，咨询必须绑定机构招生渠道，购物车商品必须来自真实班次。

Checklist：

- [x] 生成题库、题目和题目关系表。
- [x] 生成优惠券模板、适用范围和领券记录。
- [x] 生成曝光、访问、搜索、收藏、购物车、咨询记录。
- [x] 执行 Layer3 转化链路闭环、题库关系闭环和优惠券有效期校验。

### 阶段 4：Layer4 交易与履约闭环
- 目标：基于课程、班次、咨询、领券和购物车数据生成订单、支付、退款和报名关系。
- 处理表：`order`、`order_item`、`payment_record`、`refund_request`、`student_cohort_rel`

表级说明：

- `order` / `order_item`
  - 来源：程序生成。
  - 生成方式：从咨询转化、自然浏览转化、领券转化、加购转化中抽样生成订单；每个订单至少包含一条班次商品明细。
  - 关键约束：金额闭环、渠道归因口径稳定、优惠券核销状态与支付结果一致。
- `payment_record`
  - 来源：程序生成。
  - 生成方式：按订单状态生成待支付、已支付、支付失败和退款后的支付流水。
  - 关键约束：支付状态与订单状态一致，退款金额不超过支付金额。
- `refund_request`
  - 来源：程序生成。
  - 生成方式：对已支付订单明细抽样发起退款申请，覆盖待审批、已通过、已驳回、已退款场景。
  - 关键约束：退款申请金额与订单明细金额、支付流水、审批结果一致。
- `student_cohort_rel`
  - 来源：程序生成。
  - 生成方式：每条成功成交的订单明细生成一条履约关系，退款或取消时回写状态。
  - 关键约束：一条订单明细只能对应一条履约关系；同一学员同一班次只能存在一条关系。

Checklist：

- [x] 生成订单和订单明细。
- [x] 生成支付记录。
- [x] 生成退款申请。
- [x] 生成学员班次履约关系。
- [x] 执行 Layer4 金额闭环、订单状态流转、退款链路和履约唯一性校验。

### 阶段 5：Layer5 学习、互动与服务过程
- 目标：基于真实履约关系生成学习行为、互动内容和服务处理过程。
- 处理表：`session_attendance`、`session_video_play`、`session_video_play_event`、`session_homework_submission`、`session_exam_submission`、`cohort_discussion_topic`、`cohort_discussion_post`、`cohort_review`、`service_ticket`、`service_ticket_follow_record`、`service_ticket_satisfaction_survey`

表级说明：

- 学习行为组
  - 来源：程序生成。
  - 生成方式：仅对 `student_cohort_rel` 状态不为 `cancelled/refunded` 的学员生成考勤、视频、作业和考试数据。
  - 关键约束：作业和考试提交表必须覆盖课次有效学员全集，未提交或未进入考试者自动进入终态。
- 互动组
  - 来源：程序生成。
  - 生成方式：围绕班次生成讨论主题、回复和评价，覆盖学员发帖、教师回复、匿名评价等场景。
  - 关键约束：回复数、最后回复时间和逻辑删除口径一致。
- 服务组
  - 来源：程序生成。
  - 生成方式：围绕订单明细和退款申请生成售后工单、跟进记录和满意度调查。
  - 关键约束：退款类工单必须关联退款申请，满意度调查只能针对已关闭工单生成。

Checklist：

- [x] 生成考勤、视频播放、作业提交、考试作答。
- [x] 生成讨论主题、回复和班次评价。
- [x] 生成工单、跟进记录和满意度调查。
- [x] 执行 Layer5 履约前置、学习时间窗、互动统计口径和工单闭环校验。

### 阶段 6：Layer6 经营衍生结果
- 目标：基于真实交易、履约、学习、互动和服务数据生成课酬、返佣、风险预警和内容审核结果。
- 处理表：`teacher_compensation_bill`、`teacher_compensation_item`、`channel_commission_bill`、`channel_commission_item`、`risk_alert_event`、`risk_disposal_record`、`ugc_moderation_task`

表级说明：

- 课酬组
  - 来源：程序生成。
  - 生成方式：按教师、课次和结算周期汇总生成课酬账单及明细。
  - 关键约束：账单金额必须等于明细汇总，课次类明细唯一。
- 返佣组
  - 来源：程序生成。
  - 生成方式：按订单来源渠道和机构生成返佣账单与订单级返佣明细。
  - 关键约束：返佣比例使用 `0~1` 小数口径，返佣金额按四舍五入保留两位。
- 风控与审核组
  - 来源：程序生成。
  - 生成方式：从退款异常、学习异常、考试异常、UGC 内容异常、异常操作中抽样生成风险预警；从讨论、回复、评价中抽样生成审核任务。
  - 关键约束：风险对象与业务类型匹配，审核任务必须真实指向主题、回复或评价内容。

Checklist：

- [x] 生成教师课酬账单和明细。
- [x] 生成渠道返佣账单和明细。
- [x] 生成风险预警和处置记录。
- [x] 生成 UGC 审核任务。
- [x] 执行 Layer6 汇总金额、风险对象匹配和审核对象存在性校验。

### 阶段 7：最终验收
- 目标：对全量生成数据进行最终验收，不重复执行阶段内细粒度检查。
- 验收范围：全库数据。

最终验收项：

- 关键表非空：确认课程、交易、履约、学习、互动、服务、经营相关核心表均非空。
- 全局唯一性：确认编码、单号、券号、任务号、预警号等业务唯一键无重复。
- 跨域外键完整性：确认组织、课程、交易、履约、学习、互动、服务、经营之间的外键引用全部闭环。
- 时间顺序正确：确认创建时间、更新时间、支付时间、退款时间、学习时间、工单处理时间等整体有序。
- 金额闭环成立：确认订单、支付、退款、课酬、返佣等金额汇总关系全部成立。
- 履约约束成立：确认所有学习行为、评价、工单都能回溯到真实履约关系或真实订单明细。

Checklist：

- [x] 执行关键表非空校验。
- [x] 执行业务唯一键校验。
- [x] 执行跨域外键完整性校验。
- [x] 执行全局时间顺序校验。
- [x] 执行金额闭环校验。
- [x] 执行履约前置与状态一致性校验。

## 接口定义
### 公共约定
公共请求头：

- `X-User-Id`：默认必填，当前用户 ID；公共查询接口按各接口说明可不传或可选传入。

说明：

- 当前实现统一通过请求头 `X-User-Id` 传入用户 ID。
- 服务端需要校验 `X-User-Id` 是否为合法数字，且对应用户在 `sys_user` 表中真实存在并处于启用状态。
- 公共查询接口包括 `GET /api/v1/series`、`GET /api/v1/series/{series_id}`、`GET /api/v1/series/{series_id}/cohorts`、`GET /api/v1/cohorts/{cohort_id}`，这些接口不要求传 `X-User-Id`。
- 除上述公共查询接口外，其余接口都必须校验当前用户身份。

公共响应结构：

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

错误响应结构：

```json
{
  "code": "INVALID_USER_ID",
  "message": "X-User-Id 必须为合法数字",
  "data": null
}
```

---

### 1. 用户信息与学习档案查询
#### 1.1 `GET /api/v1/me`
说明：查询当前用户基础信息。

主要关联表：

- `sys_user`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "userId": 10001,
    "nickname": "小林同学",
    "realName": "林晨曦",
    "mobile": "13800000001",
    "email": "linchenxi@example.com",
    "gender": "female",
    "avatarUrl": "https://example.com/avatar/10001.jpg",
    "birthday": "2004-06-18"
  }
}
```

接口实现细节：

- 查询条件固定为 `sys_user.id = X-User-Id and sys_user.yn = 1`。
- 若用户不存在或已停用，返回 `404 NOT_FOUND`，错误码为 `USER_NOT_FOUND_OR_DISABLED`。

#### 1.2 `GET /api/v1/me/student-profile`
说明：查询当前用户学员档案、学习目标、学习者身份、学历或年级信息。

主要关联表：

- `student_profile`
- `dim_learner_identity`
- `dim_learning_goal`
- `dim_education_level`
- `dim_grade`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "studentId": 50123,
    "learnerIdentity": {
      "code": "in_school_student",
      "name": "在校生"
    },
    "learningGoal": {
      "code": "exam_preparation",
      "name": "升学备考"
    },
    "educationLevel": null,
    "grade": {
      "code": "senior_2",
      "name": "高中二年级"
    },
    "schoolName": "上海市实验中学",
    "profileNote": "目标冲刺重点高中"
  }
}
```

接口实现细节：

- 查询条件固定为 `student_profile.user_id = X-User-Id and student_profile.yn = 1`。
- 在校生返回 `grade`，非在校生返回 `educationLevel`。
- 若用户没有学员档案，返回 `404 NOT_FOUND`，错误码为 `STUDENT_PROFILE_NOT_FOUND`。

#### 1.3 `GET /api/v1/me/learning-summary`
说明：查询当前用户学习概览，仅返回聚合信息，如在读班次数、已完成班次数、最近学习记录。

主要关联表：

- `student_profile`
- `student_cohort_rel`
- `session_video_play`
- `session_homework_submission`
- `session_exam_submission`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "activeCohortCount": 2,
    "completedCohortCount": 1,
    "cancelledOrRefundedCohortCount": 0,
    "recentLearningRecords": [
      {
        "type": "video",
        "title": "函数与参数",
        "occurredAt": "2025-01-18 20:13:21"
      },
      {
        "type": "homework",
        "title": "二次函数专题作业",
        "occurredAt": "2025-01-17 21:32:10"
      }
    ]
  }
}
```

接口实现细节：

- 只返回聚合概览，不返回班次明细。
- 最近学习记录统一按最近视频播放、作业提交、考试提交的时间倒序取前 10 条。

---

### 2. 课程与班次查询
#### 2.1 `GET /api/v1/series`
说明：按关键词、分类、学习目标、授课方式等条件查询课程列表；当传入 `keyword` 时，同时承担课程搜索能力。

主要关联表：

- `series`
- `series_category_rel`
- `dim_course_category`
- `cohort_review`

请求头：

- `X-User-Id`：可选；仅当需要记录当前用户搜索日志时传入

请求参数：

- `keyword`：可选，课程名称关键字
- `categoryId`：可选，课程分类 ID
- `learningGoalCode`：可选，学习目标编码，取值包括 `score_improvement`、`school_sync`、`exam_preparation`、`postgraduate_exam`、`certificate_exam`、`skill_improvement`、`job_hunting`、`promotion`、`career_switch`、`interest_learning`、`other`
- `deliveryModeCode`：可选，授课方式编码，取值包括 `online_live`、`online_recorded`、`offline_face_to_face`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "seriesId": 9001,
        "seriesName": "高考数学冲刺班",
        "coverUrl": "https://example.com/series/9001.jpg",
        "deliveryModeCode": "online_live",
        "saleStatusCode": "on_sale",
        "avgScore": 4.8,
        "reviewCount": 126
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- 只返回 `series.sale_status = on_sale` 的课程系列。
- 课程评分使用 `cohort_review.score_overall` 做聚合计算。
- 列表排序固定为 `avgScore desc, reviewCount desc, series.id desc`。
- 当传入 `keyword` 且同时传入合法 `X-User-Id` 时，服务端在返回列表后写入一条 `series_search_log`，`search_source` 固定为 `course_list_page`，`clicked_series_id` 固定为空。

#### 2.2 `GET /api/v1/series/{series_id}`
说明：查询课程详情，包括适用人群、课程介绍、授课方式、评价摘要等。

主要关联表：

- `series`
- `series_category_rel`
- `dim_course_category`
- `cohort_review`

请求头：

- 无

请求参数：

- `series_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "seriesId": 9001,
    "seriesName": "高考数学冲刺班",
    "description": "面向高考冲刺阶段学生的系统课程",
    "deliveryModeCode": "online_live",
    "targetLearnerIdentityCodes": ["in_school_student"],
    "targetLearningGoalCodes": ["exam_preparation"],
    "targetGradeCodes": ["senior_2", "senior_3"],
    "saleStatusCode": "on_sale",
    "avgScore": 4.8,
    "reviewCount": 126
  }
}
```

接口实现细节：

- 查询条件固定为 `series.id = series_id`。
- 若课程不存在或 `series.sale_status != on_sale`，返回 `404 NOT_FOUND`，错误码为 `SERIES_NOT_FOUND`。

#### 2.3 `GET /api/v1/series/{series_id}/cohorts`
说明：查询课程下可报名班次。

主要关联表：

- `series_cohort`
- `org_campus`
- `staff_profile`
- `sys_user`

请求头：

- 无

请求参数：

- `series_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "cohortId": 30001,
      "cohortName": "2026 春季直播 1 班",
      "salePrice": 3999.00,
      "campusName": null,
      "headTeacherName": "王老师",
      "startDate": "2025-01-10",
      "endDate": "2025-03-20",
      "maxStudentCount": 80,
      "currentStudentCount": 52
    }
  ]
}
```

接口实现细节：

- 只返回 `yn = 1` 且 `current_student_count < max_student_count` 的班次。
- 录播班次 `endDate` 可为空。
- `salePrice` 直接读取 `series_cohort.sale_price`。

#### 2.4 `GET /api/v1/cohorts/{cohort_id}`
说明：查询班次详情，包括开班时间、班主任、售价、容量、课程模块与课次安排。

主要关联表：

- `series_cohort`
- `series_cohort_course`
- `series_cohort_session`
- `staff_profile`
- `sys_user`

请求头：

- 无

请求参数：

- `cohort_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "cohortId": 30001,
    "cohortName": "2026 春季直播 1 班",
    "salePrice": 3999.00,
    "startDate": "2025-01-10",
    "endDate": "2025-03-20",
    "headTeacherName": "王老师",
    "currentStudentCount": 52,
    "modules": [
      {
        "cohortCourseId": 70001,
        "moduleName": "函数与导数",
        "stageNo": 1,
        "lessonCount": 8
      }
    ],
    "sessions": [
      {
        "sessionId": 81001,
        "sessionTitle": "导数基础",
        "teachingDate": "2025-01-12",
        "startTime": "19:00:00",
        "endTime": "21:00:00"
      }
    ]
  }
}
```

接口实现细节：

- `salePrice` 直接读取 `series_cohort.sale_price`。
- 模块按 `stage_no asc` 排序。
- 课次按 `teaching_date asc, start_time asc` 排序。

---

### 3. 收藏
#### 3.1 `GET /api/v1/me/favorites`
说明：查询当前用户已收藏课程。

主要关联表：

- `series_favorite`
- `series`

请求头：

- `X-User-Id`：必填

请求参数：

- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "seriesId": 9001,
        "seriesName": "高考数学冲刺班",
        "favoriteCreatedAt": "2025-01-08 20:20:10"
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- 只返回 `series_favorite.yn = 1` 的记录。

#### 3.2 `POST /api/v1/series/{series_id}/favorite`
说明：代用户收藏课程。

主要关联表：

- `series_favorite`

请求头：

- `X-User-Id`：必填

请求参数：

- `series_id`：路径参数，必填

请求体：

```json
{
  "favoriteSource": "series_detail"
}
```

请求体字段说明：

- `favoriteSource`：收藏来源，取值包括 `series_detail`、`search_result`、`recommendation`、`activity_page`

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "favoriteId": 12345,
    "favorited": true,
    "created": true
  }
}
```

接口实现细节：

- 若用户未收藏，创建收藏记录并返回 `created = true`。
- 若用户已收藏，返回已存在的收藏记录，`created = false`，不重复创建新记录。
- `favorite_source` 固定写入调用来源。

#### 3.3 `DELETE /api/v1/series/{series_id}/favorite`
说明：代用户取消收藏课程。

主要关联表：

- `series_favorite`

请求头：

- `X-User-Id`：必填

请求参数：

- `series_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "favorited": false
  }
}
```

接口实现细节：

- 取消收藏时固定将 `series_favorite.yn` 更新为 `0`，不物理删除记录。

### 4. 咨询
#### 4.1 `POST /api/v1/cohorts/{cohort_id}/consultations`
说明：代用户发起咨询，记录咨询内容和联系方式。

主要关联表：

- `consultation_record`
- `dim_channel`

请求头：

- `X-User-Id`：必填

请求参数：

- `cohort_id`：路径参数，必填

请求体：

```json
{
  "consultChannel": "phone",
  "contactMobile": "13800000001",
  "consultContent": "想了解直播回放和作业批改安排",
  "sourceChannelId": 12
}
```

请求体字段说明：

- `consultChannel`：咨询渠道，取值包括 `phone`、`online_chat`、`wechat`、`offline_visit`
- `sourceChannelId`：来源渠道 ID，非空，必须能关联到有效的 `dim_channel.id`

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "consultationId": 88001
  }
}
```

接口实现细节：

- `sourceChannelId` 非空，必须能关联到有效的 `dim_channel.id`。
- 咨询记录默认归属于当前用户。

#### 4.2 `GET /api/v1/me/consultations`
说明：查询当前用户历史咨询记录。

主要关联表：

- `consultation_record`
- `series_cohort`

请求头：

- `X-User-Id`：必填

请求参数：

- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "consultationId": 88001,
        "cohortId": 30001,
        "consultChannel": "phone",
        "consultContent": "想了解直播回放和作业批改安排",
        "consultedAt": "2025-01-05 14:10:00"
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- 列表按 `consulted_at desc, id desc` 排序。

---

### 5. 优惠券
#### 5.1 `GET /api/v1/coupons/available`
说明：查询当前用户可领取优惠券。

主要关联表：

- `coupon`

请求头：

- `X-User-Id`：必填

请求参数：

- `seriesId`：可选
- `categoryId`：可选

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "couponId": 6001,
      "couponName": "新人立减券",
      "issuerScope": "platform",
      "discountAmount": 50.00,
      "thresholdAmount": 300.00,
      "validFrom": "2025-01-01 00:00:00",
      "validTo": "2025-01-31 23:59:59"
    }
  ]
}
```

接口实现细节：

- 只返回当前时间处于有效期内、库存未耗尽且当前用户尚未达到 `coupon.per_user_limit` 的券。
- 若传入 `seriesId` 或 `categoryId`，需额外匹配优惠券适用范围。

#### 5.2 `POST /api/v1/coupons/{coupon_id}/receive`
说明：代用户领取优惠券。

主要关联表：

- `coupon`
- `coupon_receive_record`

请求头：

- `X-User-Id`：必填

请求参数：

- `coupon_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "receiveId": 99001,
    "receiveNo": "CR0000000001"
  }
}
```

接口实现细节：

- 领取时创建 `coupon_receive_record`，初始状态为未使用。
- 当前实现按 `coupon.per_user_limit` 校验用户个人领取上限。
- 若库存不足，返回 `409 CONFLICT`，错误码为 `COUPON_OUT_OF_STOCK`。
- 若超出领取限制，返回 `409 CONFLICT`，错误码为 `COUPON_RECEIVE_LIMIT_EXCEEDED`。
- 若已过有效期，返回 `409 CONFLICT`，错误码为 `COUPON_EXPIRED`。

#### 5.3 `GET /api/v1/me/coupons`
说明：查询当前用户已领取优惠券及状态。

主要关联表：

- `coupon_receive_record`
- `coupon`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，领取状态，取值包括 `unused`、`used`、`expired`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "receiveId": 99001,
        "couponName": "新人立减券",
        "receiveStatusCode": "unused",
        "receivedAt": "2025-01-10 10:00:00",
        "usedAt": null,
        "expiredAt": "2025-01-31 23:59:59"
      }
    ]
  }
}
```

接口实现细节：

- 券状态由领取记录状态为主，不直接用模板状态代替。

### 6. 购物车
#### 6.1 `GET /api/v1/cart/items`
说明：查询当前用户购物车。

主要关联表：

- `shopping_cart_item`
- `series_cohort`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "itemId": 42001,
      "cohortId": 30001,
      "cohortName": "2026 春季直播 1 班",
      "unitPrice": 999.00,
      "addedAt": "2025-01-15 11:22:00"
    }
  ]
}
```

接口实现细节：

- 只返回未移除的购物车项。

#### 6.2 `POST /api/v1/cart/items`
说明：代用户加入购物车。

主要关联表：

- `shopping_cart_item`
- `series_cohort`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

```json
{
  "cohortId": 30001,
  "cartSource": "series_detail"
}
```

请求体字段说明：

- `cartSource`：加入来源，取值包括 `series_detail`、`search_result`、`recommendation`、`activity_page`

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "itemId": 42001
  }
}
```

接口实现细节：

- 若同一用户对同一班次已存在未移除购物车项，返回该购物车项，不重复创建新记录。

#### 6.3 `DELETE /api/v1/cart/items/{item_id}`
说明：代用户移出购物车。

主要关联表：

- `shopping_cart_item`

请求头：

- `X-User-Id`：必填

请求参数：

- `item_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "removed": true
  }
}
```

接口实现细节：

- 移出购物车时固定写入 `removed_at = 当前时间`，不物理删除记录。

### 7. 订单
#### 7.1 `POST /api/v1/orders/quote`
说明：试算某个班次的原价、优惠金额、应付金额和可用优惠券。

主要关联表：

- `series_cohort`
- `coupon`
- `coupon_receive_record`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

```json
{
  "cohortId": 30001,
  "couponReceiveRecordId": 99001
}
```

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "cohortId": 30001,
    "totalAmount": 3999.00,
    "discountAmount": 50.00,
    "payableAmount": 3949.00,
    "availableCoupons": [
      {
        "couponReceiveRecordId": 99001,
        "couponName": "新人立减券",
        "couponType": "cash",
        "discountAmount": 50.00,
        "expiredAt": "2025-02-01 23:59:59"
      }
    ]
  }
}
```

接口实现细节：

- `totalAmount` 直接读取 `series_cohort.sale_price`。
- 若传入优惠券，必须校验该券属于当前用户、未使用且未过期，并且适用于当前班次。
- 试算接口不落库，不改变优惠券状态。

#### 7.2 `POST /api/v1/orders`
说明：代用户创建订单。

主要关联表：

- `order`
- `order_item`
- `student_profile`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

```json
{
  "studentId": 50123,
  "cohortId": 30001,
  "couponReceiveRecordId": 99001,
  "orderSourceChannelId": 12,
  "remark": "客服协助下单"
}
```

请求体字段说明：

- `orderSourceChannelId`：订单来源渠道 ID，可选；由调用程序根据咨询记录、活动链接、投放归因、私域分享、加购来源等上下文传入，不由用户手工选择

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "orderId": 70001,
    "orderNo": "ORD0000000001",
    "orderStatusCode": "pending",
    "payableAmount": 3949.00
  }
}
```

接口实现细节：

- `studentId` 必须属于当前用户。
- 创建订单时同步生成一条订单明细。
- 订单金额和订单明细单价直接读取 `series_cohort.sale_price`，再叠加优惠券计算 `discountAmount` 和 `payableAmount`。
- 优惠券只在订单创建成功时占用，不在试算阶段占用。
- 若传入优惠券，必须校验该券适用于当前班次。
- `orderSourceChannelId` 不为空时，必须能关联到有效的 `dim_channel.id`。
- `orderSourceChannelId` 为空时，表示本次订单未命中明确渠道归因，或用户直接在应用内自然浏览、搜索、加购后完成下单。
- 当前实现中，若当前用户在该班次下已存在咨询记录，则传入的 `orderSourceChannelId` 必须匹配该用户该班次任一 `consultation_record.source_channel_id`。

#### 7.3 `GET /api/v1/orders`
说明：查询当前用户订单列表。

主要关联表：

- `order`
- `order_item`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，订单状态，取值包括 `pending`、`paid`、`completed`、`cancelled`、`partial_refunded`、`refunded`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "orderId": 70001,
        "orderNo": "ORD0000000001",
        "orderStatusCode": "paid",
        "payableAmount": 3949.00,
        "paidAmount": 3949.00,
        "createdAt": "2025-01-20 10:10:00"
      }
    ]
  }
}
```

接口实现细节：

- 列表按 `created_at desc, id desc` 排序。

#### 7.4 `GET /api/v1/orders/{order_id}`
说明：查询订单详情，包括订单状态、金额、优惠信息、支付摘要和退款摘要。

主要关联表：

- `order`
- `order_item`
- `payment_record`
- `refund_request`

请求头：

- `X-User-Id`：必填

请求参数：

- `order_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "orderId": 70001,
    "orderNo": "ORD0000000001",
    "orderStatusCode": "paid",
    "totalAmount": 3999.00,
    "discountAmount": 50.00,
    "payableAmount": 3949.00,
    "paidAmount": 3949.00,
    "paymentSummary": {
      "paymentStatusCode": "paid",
      "paidAt": "2025-01-20 10:20:00"
    },
    "refundSummary": {
      "refundRequestCount": 0,
      "refundAmount": 0.00
    }
  }
}
```

接口实现细节：

- 订单必须属于当前用户。
- 支付摘要取最新支付记录。
- 退款摘要按订单下退款申请聚合计算。

#### 7.5 `POST /api/v1/orders/{order_id}/cancel`
说明：代用户取消未支付订单。

主要关联表：

- `order`

请求头：

- `X-User-Id`：必填

请求参数：

- `order_id`：路径参数，必填

请求体：

```json
{
  "reason": "暂不报名"
}
```

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "orderId": 70001,
    "orderStatusCode": "cancelled"
  }
}
```

接口实现细节：

- 只允许取消未支付订单。
- 若订单已支付，需引导走退款申请流程。

---

### 8. 支付与退款
#### 8.1 `POST /api/v1/orders/{order_id}/payments`
说明：为订单创建一笔支付请求，返回支付单信息和拉起支付所需参数。

主要关联表：

- `order`
- `payment_record`

请求头：

- `X-User-Id`：必填

请求参数：

- `order_id`：路径参数，必填

请求体：

```json
{
  "paymentChannelCode": "wechat_pay"
}
```

请求体字段说明：

- `paymentChannelCode`：支付渠道，取值包括 `wechat_pay`、`alipay`、`bank_card`

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "paymentId": 80001,
    "paymentNo": "PAY0000000001",
    "paymentStatusCode": "pending",
    "paymentChannelCode": "wechat_pay",
    "amount": 3949.00,
    "paymentParams": {
      "mockToken": "MOCK_PAY_TOKEN_80001"
    },
    "createdAt": "2025-01-20 10:20:00"
  }
}
```

接口实现细节：

- 订单必须属于当前用户，且订单状态必须为 `pending`。
- 当前订单若已存在未关闭的待支付支付单，可直接返回最近一笔待支付支付单，不重复创建新支付单。
- 创建支付单阶段不直接把订单改成 `paid`，订单仍保持 `pending`。
- `paymentParams` 为调用支付渠道 SDK 或跳转收银台所需参数；演示系统可返回 mock 参数。

#### 8.2 `GET /api/v1/orders/{order_id}/payments`
说明：查询订单下的支付记录列表。

主要关联表：

- `order`
- `payment_record`

请求头：

- `X-User-Id`：必填

请求参数：

- `order_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "paymentId": 80001,
        "paymentNo": "PAY0000000001",
        "paymentChannelCode": "wechat_pay",
        "paymentStatusCode": "paid",
        "amount": 3949.00,
        "thirdPartyTradeNo": "TP_DEMO_0001",
        "paidAt": "2025-01-20 10:25:00",
        "createdAt": "2025-01-20 10:20:00"
      }
    ]
  }
}
```

接口实现细节：

- 订单必须属于当前用户。
- 列表按 `created_at desc, id desc` 排序。

#### 8.3 `GET /api/v1/payments/{payment_id}`
说明：查询单笔支付详情。

主要关联表：

- `payment_record`
- `order`

请求头：

- `X-User-Id`：必填

请求参数：

- `payment_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "paymentId": 80001,
    "paymentNo": "PAY0000000001",
    "orderId": 70001,
    "paymentChannelCode": "wechat_pay",
    "paymentStatusCode": "paid",
    "amount": 3949.00,
    "thirdPartyTradeNo": "TP_DEMO_0001",
    "refundAmount": 0.00,
    "paidAt": "2025-01-20 10:25:00",
    "refundAt": null,
    "createdAt": "2025-01-20 10:20:00"
  }
}
```

接口实现细节：

- 支付记录必须通过所属订单归属于当前用户。

#### 8.4 `POST /api/v1/payments/{payment_id}/close`
说明：关闭未支付的支付单。关闭支付单不直接取消订单，订单仍保持待支付状态。

主要关联表：

- `payment_record`
- `order`

请求头：

- `X-User-Id`：必填

请求参数：

- `payment_id`：路径参数，必填

请求体：

```json
{
  "closeReason": "user_cancel"
}
```

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "paymentId": 80001,
    "paymentNo": "PAY0000000001",
    "orderId": 70001,
    "paymentStatusCode": "closed",
    "updatedAt": "2025-01-20 10:24:00"
  }
}
```

接口实现细节：

- 支付记录必须通过所属订单归属于当前用户。
- 只允许将 `payment_status = pending` 的支付单更新为 `closed`。
- 支付单已是 `paid`、`failed`、`closed`、`partial_refunded` 或 `refunded` 时，按幂等规则返回当前状态，不重复更新。

#### 8.5 `POST /api/v1/payment-notifications/mock`
说明：模拟支付渠道异步回调，通知服务端某笔支付成功、失败或关闭。

主要关联表：

- `payment_record`
- `order`
- `order_item`
- `coupon_receive_record`

请求头：

- `X-Demo-Payment-Signature`：必填，支付通知签名，默认值为 `mock-payment-signature`

请求参数：

- 无

请求体：

```json
{
  "paymentNo": "PAY0000000001",
  "orderId": 70001,
  "paymentChannelCode": "wechat_pay",
  "amount": 3949.00,
  "tradeStatus": "paid",
  "thirdPartyTradeNo": "TP_DEMO_0001"
}
```

请求体字段说明：

- `paymentChannelCode`：支付渠道，取值包括 `wechat_pay`、`alipay`、`bank_card`
- `tradeStatus`：交易状态，取值包括 `paid`、`failed`、`closed`

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "paymentId": 80001,
    "paymentStatusCode": "paid",
    "orderId": 70001,
    "orderStatusCode": "paid",
    "processed": true
  }
}
```

接口实现细节：

- 支付通知接口不读取 `X-User-Id`，只校验 `X-Demo-Payment-Signature`。
- 服务端先按 `paymentNo` 查询支付记录，并校验 `orderId`、`paymentChannelCode`、`amount` 与库中支付记录一致。
- 服务端必须按 `paymentNo` 做幂等处理，同一支付通知重复调用不能重复入账，重复通知返回 `processed = false`。
- `tradeStatus = paid` 时，需同步更新 `payment_record`、`order`、`order_item`。
- `tradeStatus = failed` 时，更新 `payment_record.payment_status = failed`，订单保持 `pending`。
- `tradeStatus = closed` 时，更新 `payment_record.payment_status = closed`，订单保持 `pending`。
- 订单使用了优惠券时，只有在支付成功回调后才把对应 `coupon_receive_record` 更新为 `used`。

#### 8.6 `POST /api/v1/order-items/{order_item_id}/refund-requests`
说明：代用户提交退款申请。

主要关联表：

- `refund_request`
- `order_item`
- `payment_record`

请求头：

- `X-User-Id`：必填

请求参数：

- `order_item_id`：路径参数，必填

请求体：

```json
{
  "refundType": "personal_reason",
  "refundReason": "时间冲突无法继续学习",
  "applyAmount": 949.00,
  "remark": "客服代提交"
}
```

请求体字段说明：

- `refundType`：退款类型，取值包括 `personal_reason`、`course_unsatisfied`、`schedule_conflict`、`duplicate_purchase`

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "refundRequestId": 87001,
    "refundNo": "RF0000000001",
    "refundStatusCode": "pending"
  }
}
```

接口实现细节：

- 订单明细必须属于当前用户。
- 申请金额不能超过可退金额。
- 已存在处理中退款申请时，不允许重复提交。

#### 8.7 `GET /api/v1/refund-requests`
说明：查询当前用户退款申请列表。

主要关联表：

- `refund_request`
- `order_item`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，退款状态，取值包括 `pending`、`approved`、`rejected`、`refunded`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "refundRequestId": 87001,
        "refundNo": "RF0000000001",
        "refundStatusCode": "pending",
        "applyAmount": 949.00,
        "approvedAmount": null,
        "appliedAt": "2025-01-20 11:00:00"
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- 列表按 `applied_at desc, id desc` 排序。

#### 8.8 `GET /api/v1/refund-requests/{refund_request_id}`
说明：查询退款申请详情、审批结果和退款进度。

主要关联表：

- `refund_request`

请求头：

- `X-User-Id`：必填

请求参数：

- `refund_request_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "refundRequestId": 87001,
    "refundNo": "RF0000000001",
    "refundStatusCode": "approved",
    "applyAmount": 949.00,
    "approvedAmount": 900.00,
    "appliedAt": "2025-01-20 11:00:00",
    "approvedAt": "2025-01-21 09:30:00",
    "refundedAt": null
  }
}
```

接口实现细节：

- 退款申请必须属于当前用户。

---

### 9. 报名关系与学习中心
#### 9.1 `GET /api/v1/me/cohorts`
说明：查询当前用户已报名、在读、已完成、已取消、已退费的班次。

主要关联表：

- `student_cohort_rel`
- `series_cohort`
- `series`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，履约状态，取值包括 `active`、`completed`、`cancelled`、`refunded`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "cohortId": 30001,
        "cohortName": "2026 春季直播 1 班",
        "seriesName": "高考数学冲刺班",
        "enrollStatusCode": "active",
        "enrollAt": "2025-01-20 10:20:00"
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- 基于 `student_cohort_rel.user_id = X-User-Id` 查询。

#### 9.2 `GET /api/v1/me/cohorts/{cohort_id}`
说明：查询用户在某个班次下的履约状态、服务周期、完成状态。

主要关联表：

- `student_cohort_rel`

请求头：

- `X-User-Id`：必填

请求参数：

- `cohort_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "cohortId": 30001,
    "enrollStatusCode": "active",
    "enrollAt": "2025-01-20 10:20:00",
    "serviceEndAt": null,
    "completedAt": null
  }
}
```

接口实现细节：

- 当前用户必须存在该班次履约关系。

#### 9.3 `GET /api/v1/me/cohorts/{cohort_id}/sessions`
说明：查询当前用户在某个班次下的课次列表，并附带个人学习状态。

主要关联表：

- `series_cohort_session`
- `session_attendance`
- `session_homework_submission`
- `session_exam_submission`

请求头：

- `X-User-Id`：必填

请求参数：

- `cohort_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "sessionId": 81001,
      "sessionTitle": "导数基础",
      "teachingDate": "2025-01-12",
      "attendanceStatusCode": "present",
      "homeworkSubmitStatus": "submitted",
      "examAttemptStatus": null
    }
  ]
}
```

接口实现细节：

- 课次列表按时间顺序返回。
- 个人状态信息按当前用户对应的学员档案聚合。

#### 9.4 `GET /api/v1/me/cohorts/{cohort_id}/progress`
说明：查询当前用户在某个班次下的综合学习进度，包括出勤、视频、作业、考试和当前履约状态。

主要关联表：

- `student_cohort_rel`
- `session_attendance`
- `session_video_play`
- `session_homework_submission`
- `session_exam_submission`

请求头：

- `X-User-Id`：必填

请求参数：

- `cohort_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "enrollStatusCode": "active",
    "attendance": {
      "totalSessions": 24,
      "presentCount": 20,
      "absentCount": 1
    },
    "video": {
      "totalVideos": 18,
      "completedVideos": 12,
      "watchedSeconds": 12600
    },
    "homework": {
      "totalHomeworks": 6,
      "submittedCount": 5,
      "correctedCount": 4,
      "expiredUnsubmittedCount": 1
    },
    "exam": {
      "totalExams": 2,
      "submittedCount": 1,
      "absentCount": 0
    }
  }
}
```

接口实现细节：

- 该接口返回综合进度，不返回课次明细。
- 班次明细应通过 `/me/cohorts/{cohort_id}/sessions` 获取。

---

### 10. 课次、视频、作业、考试
#### 10.1 `GET /api/v1/sessions/{session_id}`
说明：查询课次详情。

主要关联表：

- `series_cohort_session`
- `session_teacher_rel`
- `staff_profile`
- `sys_user`

请求头：

- `X-User-Id`：必填

请求参数：

- `session_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "sessionId": 81001,
    "sessionTitle": "导数基础",
    "teachingDate": "2025-01-12",
    "startTime": "19:00:00",
    "endTime": "21:00:00",
    "teachingStatusCode": "finished",
    "teachers": [
      {
        "staffId": 40021,
        "teacherName": "李老师"
      }
    ]
  }
}
```

接口实现细节：

- 当前用户必须对该课次所属班次存在履约关系，且状态不能为取消或退费。

#### 10.2 `GET /api/v1/videos/{video_id}`
说明：查询视频详情和可播放信息。

主要关联表：

- `session_video`
- `session_asset`

请求头：

- `X-User-Id`：必填

请求参数：

- `video_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "videoId": 91001,
    "videoTitle": "导数基础视频课",
    "durationSeconds": 3600,
    "resolutionLabel": "1080p",
    "fileUrl": "https://example.com/video/91001.m3u8"
  }
}
```

接口实现细节：

- 视频关联课次所属班次必须存在当前用户的 `student_cohort_rel`，且履约状态不能为 `cancelled` 或 `refunded`。

#### 10.3 `GET /api/v1/videos/{video_id}/chapters`
说明：查询视频章节。

主要关联表：

- `session_video_chapter`

请求头：

- `X-User-Id`：必填

请求参数：

- `video_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "chapterNo": 1,
      "chapterTitle": "导数定义",
      "startSecond": 0,
      "endSecond": 600
    }
  ]
}
```

接口实现细节：

- 章节按 `chapter_no asc` 排序。

#### 10.4 `GET /api/v1/me/video-history`
说明：查询当前用户视频学习记录。

主要关联表：

- `session_video_play`
- `session_video`

请求头：

- `X-User-Id`：必填

请求参数：

- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "videoId": 91001,
        "videoTitle": "导数基础视频课",
        "lastPositionSeconds": 1200,
        "progressPercent": 33.3,
        "updatedAt": "2025-01-18 20:13:21"
      }
    ]
  }
}
```

接口实现细节：

- 以最近一次播放会话或最新更新时间作为排序依据。

#### 10.5 `GET /api/v1/me/homeworks`
说明：查询当前用户相关作业列表，包括待提交、已提交、过期未提交。

主要关联表：

- `session_homework`
- `session_homework_submission`
- `series_cohort_session`
- `student_cohort_rel`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，作业状态，取值包括 `pending`、`submitted`、`expired_unsubmitted`
- `cohortId`：可选，班次 ID
- `dueBefore`：可选，截止时间上限，格式 `YYYY-MM-DD HH:mm:ss`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "homeworkId": 93001,
        "homeworkName": "导数基础作业",
        "cohortId": 30001,
        "sessionId": 81001,
        "dueAt": "2025-01-15 23:59:59",
        "homeworkStatus": "pending",
        "submissionId": null,
        "submittedAt": null,
        "correctedAt": null,
        "totalScore": null
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- 只返回当前用户存在有效履约关系的班次下的作业。
- 有效履约关系指 `student_cohort_rel.enroll_status` 不等于 `cancelled` 或 `refunded`。
- `pending` 表示当前时间未超过作业截止时间，且当前用户尚未提交。
- 默认排序固定为 `due_at asc, homework_id asc`，用于优先展示最近待处理作业。

#### 10.6 `GET /api/v1/homeworks/{homework_id}`
说明：查询作业详情。

主要关联表：

- `session_homework`

请求头：

- `X-User-Id`：必填

请求参数：

- `homework_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "homeworkId": 93001,
    "homeworkName": "导数基础作业",
    "dueAt": "2025-01-15 23:59:59",
    "createdAt": "2025-01-12 21:30:00"
  }
}
```

接口实现细节：

- 当前用户必须对作业所属课次有有效履约关系。

#### 10.7 `GET /api/v1/me/homework-submissions`
说明：查询当前用户作业提交记录与批改结果。

主要关联表：

- `session_homework_submission`
- `session_homework`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，作业提交状态，取值包括 `submitted`、`expired_unsubmitted`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "submissionId": 95001,
        "homeworkId": 93001,
        "homeworkName": "导数基础作业",
        "submitStatus": "submitted",
        "correctionStatus": "corrected",
        "totalScore": 92.0,
        "submittedAt": "2025-01-14 20:00:00",
        "correctedAt": "2025-01-15 10:30:00"
      }
    ]
  }
}
```

接口实现细节：

- 列表按 `submitted_at desc, id desc` 排序。

#### 10.8 `GET /api/v1/me/exams`
说明：查询当前用户相关考试列表，包括未开始、作答中、已提交、缺考、超时交卷。

主要关联表：

- `session_exam`
- `session_exam_submission`
- `series_cohort_session`
- `student_cohort_rel`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，考试状态，取值包括 `not_started`、`in_progress`、`submitted`、`absent`、`timeout`
- `cohortId`：可选，班次 ID
- `deadlineBefore`：可选，截止时间上限，格式 `YYYY-MM-DD HH:mm:ss`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "examId": 94001,
        "examName": "导数基础测验",
        "cohortId": 30001,
        "sessionId": 81001,
        "windowStartAt": "2025-01-16 00:00:00",
        "deadlineAt": "2025-01-18 23:59:59",
        "durationMinutes": 90,
        "attemptStatus": "not_started",
        "submissionId": null,
        "scoreValue": null
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- 只返回当前用户存在有效履约关系的班次下的考试。
- 有效履约关系指 `student_cohort_rel.enroll_status` 不等于 `cancelled` 或 `refunded`。
- 若当前用户尚无考试作答记录，返回 `attemptStatus = not_started`。
- 默认排序固定为 `deadline_at asc, exam_id asc`，用于优先展示最近待处理考试。

#### 10.9 `GET /api/v1/exams/{exam_id}`
说明：查询考试详情，包括考试窗口和时长。

主要关联表：

- `session_exam`

请求头：

- `X-User-Id`：必填

请求参数：

- `exam_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "examId": 94001,
    "examName": "导数基础测验",
    "totalScore": 100.0,
    "passScore": 60.0,
    "durationMinutes": 90,
    "windowStartAt": "2025-01-16 00:00:00",
    "deadlineAt": "2025-01-18 23:59:59"
  }
}
```

接口实现细节：

- 当前用户必须对考试所属课次有有效履约关系。

#### 10.10 `GET /api/v1/me/exam-submissions`
说明：查询当前用户考试作答记录与得分。

主要关联表：

- `session_exam_submission`
- `session_exam`

请求头：

- `X-User-Id`：必填

请求参数：

- `status`：可选，考试作答状态，取值包括 `not_started`、`in_progress`、`submitted`、`absent`、`timeout`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "submissionId": 96001,
        "examId": 94001,
        "examName": "导数基础测验",
        "attemptStatus": "submitted",
        "scoreValue": 88.0,
        "startAt": "2025-01-17 20:00:00",
        "submitAt": "2025-01-17 21:10:00"
      }
    ]
  }
}
```

接口实现细节：

- 只返回当前用户对应的考试作答记录。

---

### 11. 互动与评价
#### 11.1 `POST /api/v1/cohorts/{cohort_id}/reviews`
说明：代用户提交班次评价。

主要关联表：

- `cohort_review`
- `student_cohort_rel`

请求头：

- `X-User-Id`：必填

请求参数：

- `cohort_id`：路径参数，必填

请求体：

```json
{
  "scoreOverall": 5,
  "scoreTeacher": 5,
  "scoreContent": 4,
  "scoreService": 5,
  "reviewTags": ["讲解清晰", "服务及时"],
  "reviewContent": "老师讲解很细致，服务响应也很快",
  "anonymousFlag": 1
}
```

请求体字段说明：

- `scoreOverall`、`scoreTeacher`、`scoreContent`、`scoreService`：评分，取值范围为 `1` 到 `5`
- `anonymousFlag`：是否匿名，取值为 `0` 或 `1`

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "reviewId": 98001,
    "reviewNo": "RV0000000001"
  }
}
```

接口实现细节：

- 当前用户必须对该班次存在非取消、非退费履约关系。
- 同一用户对同一班次只允许一条有效评价。

#### 11.2 `GET /api/v1/cohorts/{cohort_id}/reviews`
说明：查询班次评价列表；如需查询当前用户自己的评价，可在结果中按当前用户过滤。

主要关联表：

- `cohort_review`

请求头：

- `X-User-Id`：可选

请求参数：

- `cohort_id`：路径参数，必填
- `onlyMine`：可选，默认 `false`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "reviewId": 98001,
        "scoreOverall": 5,
        "reviewTags": ["讲解清晰", "服务及时"],
        "reviewContent": "老师讲解很细致，服务响应也很快",
        "reviewedAt": "2025-01-18 18:00:00"
      }
    ],
    "pageNo": 1,
    "pageSize": 20,
    "total": 1
  }
}
```

接口实现细节：

- `onlyMine = true` 时必须传 `X-User-Id`。
- 匿名评价不返回真实用户信息。

---

### 12. 工单与售后服务
#### 12.1 `GET /api/v1/service-tickets`
说明：查询当前用户工单列表。

主要关联表：

- `service_ticket`

请求头：

- `X-User-Id`：必填

请求参数：

- `ticketType`：可选，工单类型，取值包括 `after_sales`、`complaint`、`refund`
- `ticketStatus`：可选，工单状态，取值包括 `pending`、`in_progress`、`closed`
- `pageNo`：可选，默认 `1`
- `pageSize`：可选，默认 `20`

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "list": [
      {
        "ticketId": 99001,
        "ticketNo": "TK0000000001",
        "ticketType": "after_sales",
        "ticketStatus": "pending",
        "title": "申请退课",
        "openedAt": "2025-01-20 12:00:00"
      }
    ]
  }
}
```

接口实现细节：

- 列表按 `opened_at desc, id desc` 排序。

#### 12.2 `POST /api/v1/service-tickets`
说明：代用户创建售后、投诉、退款相关工单。

主要关联表：

- `service_ticket`
- `refund_request`

请求头：

- `X-User-Id`：必填

请求参数：

- 无

请求体：

```json
{
  "ticketType": "refund",
  "priorityLevel": "high",
  "ticketSource": "customer_service",
  "title": "申请人工加急退款",
  "ticketContent": "已经提交退款申请，希望尽快处理",
  "studentId": 50123,
  "orderItemId": 71001,
  "refundRequestId": 87001
}
```

请求体字段说明：

- `ticketType`：工单类型，取值包括 `after_sales`、`complaint`、`refund`
- `priorityLevel`：优先级，取值包括 `low`、`medium`、`high`、`urgent`
- `ticketSource`：工单来源，本接口仅允许 `user_app`、`customer_service`；`system_auto`、`admin_manual` 仅由系统任务或后台管理流程写入

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "ticketId": 99001,
    "ticketNo": "TK0000000001",
    "ticketStatus": "pending"
  }
}
```

接口实现细节：

- `ticketType = refund` 时，`refundRequestId` 非空。
- 订单明细、退款申请、学员档案都必须属于当前用户。

#### 12.3 `GET /api/v1/service-tickets/{ticket_id}`
说明：查询工单详情。

主要关联表：

- `service_ticket`

请求头：

- `X-User-Id`：必填

请求参数：

- `ticket_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "ticketId": 99001,
    "ticketNo": "TK0000000001",
    "ticketType": "refund",
    "ticketStatus": "in_progress",
    "title": "申请人工加急退款",
    "ticketContent": "已经提交退款申请，希望尽快处理",
    "refundRequestId": 87001,
    "openedAt": "2025-01-20 12:00:00",
    "closedAt": null
  }
}
```

接口实现细节：

- 工单必须属于当前用户。

#### 12.4 `GET /api/v1/service-tickets/{ticket_id}/follow-records`
说明：查询工单跟进记录。

主要关联表：

- `service_ticket_follow_record`

请求头：

- `X-User-Id`：必填

请求参数：

- `ticket_id`：路径参数，必填

请求体：

- 无

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "followRecordId": 99501,
      "followType": "status_update",
      "followChannel": "phone",
      "followResult": "processing",
      "followContent": "客服已受理，正在核实退款进度",
      "followedAt": "2025-01-20 14:00:00"
    }
  ]
}
```

接口实现细节：

- 跟进记录按 `followed_at asc, id asc` 排序。

#### 12.5 `POST /api/v1/service-tickets/{ticket_id}/satisfaction-surveys`
说明：代用户提交满意度评价。

主要关联表：

- `service_ticket_satisfaction_survey`
- `service_ticket`

请求头：

- `X-User-Id`：必填

请求参数：

- `ticket_id`：路径参数，必填

请求体：

```json
{
  "scoreValue": 5,
  "commentText": "处理及时，沟通顺畅"
}
```

响应体：

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "surveyId": 99601
  }
}
```

接口实现细节：

- 只有已关闭工单允许提交满意度评价。
- 同一工单只允许提交一条有效满意度记录。
