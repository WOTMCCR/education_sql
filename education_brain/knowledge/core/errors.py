# knowledge/core/errors.py


class KnowledgeBaseError(Exception):
    """项目所有业务异常的基类"""

    def __init__(self, message: str = "", detail: str = ""):
        self.message = message
        self.detail = detail
        super().__init__(message)


class ParseError(KnowledgeBaseError):
    """数据解析失败（课程目录/题库/文档格式异常）"""


class StorageError(KnowledgeBaseError):
    """存储层操作失败（MongoDB/Milvus/MinIO）"""


class IngestError(KnowledgeBaseError):
    """导入流程失败"""


class SearchError(KnowledgeBaseError):
    """查询流程失败"""
