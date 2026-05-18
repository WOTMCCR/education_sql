# knowledge/processor/catalog_store.py
"""课程目录 MongoDB 写入 — 对应 PLAN.md §6.2 步骤4"""

import logging

from pymongo.database import Database

from knowledge.models.course import CourseModule , CourseSeries

logger = logging.getLogger(__name__)

def save_catalog(
    db : Database,
    series_list: list[CourseSeries],
    module_list: list[CourseModule],
)->tuple[int , int] :
    """将解析结果写入 MongoDB，返回 (upserted_series, upserted_modules)。

    写入策略：按 series_code / module_code 做 upsert（幂等）。
    重复导入不会产生重复数据，字段值以最新导入为准。
    """
    col_series = db["course_series"]
    col_module = db["course_module"]

    # 写入系列
    # 如需批量可以考虑 bulk_write
    series_ok = 0
    for s in series_list:
        doc = s.model_dump()
        col_series.update_one(
            {"series_code" : s.series_code},
            {"$set" : doc},
            upsert=True,
        )
        series_ok += 1
    
    module_ok = 0
    for m in module_list:
        doc = m.model_dump()
        col_module.update_one(
            {"module_code": m.module_code},
            {"$set": doc},
            upsert=True,
        )
        module_ok += 1
    
    # 建索引(幂等 , 已存在不会重建)
    col_series.create_index("series_code", unique=True)
    col_series.create_index("category_path")
    col_series.create_index("audience")
    col_series.create_index("goal_tags")

    col_module.create_index("module_code", unique=True)
    col_module.create_index("series_code")

    logger.info("MongoDB 写入完成: %d 系列, %d 模块", series_ok, module_ok)
    return series_ok , module_ok