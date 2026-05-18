"""题库领域数据模型 — 对应 PLAN.md §5.2"""

from pydantic import BaseModel, Field

class QuestionBank(BaseModel):
    """题库 — 来自 题目资料.md 的 ## 级别
    
    示例:
    ## 通用程序设计题库

    - 题库编码: general_purpose_programming_bank
    """
    bank_code: str
    bank_name: str
    domain_tags: list[str] = Field(default_factory=list)
    question_count: int = 0

class QuestionOption(BaseModel):
    """选项"""
    label: str
    content: str

class QuestionItem(BaseModel):
    """题目 — 来自 ### question_code 级别
    示例:
    ### general_purpose_programming_bank_q002

    - **题型**: 单选题
    - **题干**: 关于数据类型转换，下面哪种做法最稳妥？
    - **选项**:
    A. 直接把任意文本当作数字参与运算
    B. 在转换前先校验输入格式，再执行显式转换
    C. 只要能运行，所有转换都可以忽略异常
    D. 所有语言都会自动处理错误格式
    - **答案**: B
    - **解析**: 显式校验后再转换，可以减少运行时错误并让问题更容易定位。
    """
    question_code: str
    bank_code: str
    question_type: str = ""
    stem: str = ""
    options: list[QuestionOption] = Field(default_factory=list)
    answer_key: str = ""
    reference_answer: str = ""
    analysis: str = ""
    raw_block: str = ""
    quality_flags: list[str] = Field(default_factory=list)