# knowledge/processor/question_store.py
"""题库 MongoDB 写入 — 对应 PLAN.md §6.3"""

import logging

from pymongo.database import Database

from knowledge.models.question import QuestionBank, QuestionItem

logger = logging.getLogger(__name__)

def save_questions(
    db : Database,
    bank_list : list[QuestionBank],
    item_list : list[QuestionItem],
)->tuple[int , int]:
    """写入 MongoDB，返回 (upserted_banks, upserted_items)"""
    col_bank = db["question_bank"]
    col_item = db["question_item"]

    bank_ok = 0
    for b in bank_list:
        col_bank.update_one(
            {"bank_code": b.bank_code},
            {"$set": b.model_dump()},
            upsert=True,
        )
        bank_ok += 1
    
    item_ok = 0
    for q in item_list:
        col_item.update_one(
            {"question_code": q.question_code},
            {"$set": q.model_dump()},
            upsert=True,
        )
        item_ok += 1
    
    col_bank.create_index("bank_code", unique=True)
    col_item.create_index("question_code", unique=True)
    col_item.create_index("bank_code")
    col_item.create_index("question_type")

    logger.info("MongoDB 写入完成: %d 题库, %d 题目", bank_ok, item_ok)
    return bank_ok, item_ok
