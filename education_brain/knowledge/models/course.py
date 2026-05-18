"""课程领域数据模型"""
from pydantic import BaseModel, Field

class CourseSeries(BaseModel):
    """课程系列 - 来自 课程介绍.md 的 ## 级别

    示例:
    ## 通用编程入门班

    - **系列编码**: general_purpose_programming_foundation
    - **描述**: 计算机科学能力线 / 通用程序设计 / 通用编程入门班
    - **课程分类**: 计算机 / 编程语言 / 通用程序设计
    - **适合人群**: 在校生, 职场人, 求职者
    - **学习目标**: 技能提升, 求职上岸, 转岗转行
    - **适合年级**: 专科, 本科
    """

    series_code : str               # 唯一课程编码
    title : str
    description: str = ""
    category_path : str = ""
    audience: list[str] = Field(default_factory=list)
    goal_tags: list[str] = Field(default_factory=list)
    grade_tags: list[str] = Field(default_factory=list)

class CourseModule(BaseModel):
    """课程模块 — 来自 ### 课程 下的列表项

    示例:
    ### 课程

    - **面向对象与常用库实践**
    - 编码: general_purpose_programming_practice_m1, 课时: 8, 学时: 16.00
    - 描述: 通用程序设计 / 项目实践 / 工程能力
    - **命令行工具与文件处理**
    - 编码: general_purpose_programming_practice_m2, 课时: 10, 学时: 20.00
    - 描述: 通用程序设计 / 项目实践 / 工程能力
    - **综合项目开发与讲评**
    - 编码: general_purpose_programming_practice_m3, 课时: 12, 学时: 24.00
    - 描述: 通用程序设计 / 项目实践 / 工程能力
    """

    module_code: str                # 唯一编码
    series_code: str                # 所属系列编码（外键）
    module_title: str
    lesson_count: int = 0
    study_hours: float = 0.0
    module_desc: str = ""           # 课程描述
    sort_order: int = 0             # 在系列内的排序（从 `_m1` 后缀推断）