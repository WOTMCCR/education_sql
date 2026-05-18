"""Layer1: base dimensions and organization master data."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from ..insert_support import build_insert_sql, insert_dict_rows
from .base import BaseGenerator
from .seed_importer import SeedImporter
from .validations import validate_layer1


@dataclass(frozen=True)
class RoleSpec:
    code: str
    name: str
    category: str


ROLE_SPECS = (
    RoleSpec("teacher_primary", "主讲教师", "teacher"),
    RoleSpec("teacher_assistant", "助教", "teacher"),
    RoleSpec("academic_advisor", "教务老师", "academic"),
    RoleSpec("academic_manager", "教务主管", "academic"),
    RoleSpec("sales_consultant", "课程顾问", "sales"),
    RoleSpec("sales_manager", "销售主管", "sales"),
    RoleSpec("operations_specialist", "运营专员", "operations"),
    RoleSpec("service_specialist", "客服专员", "service"),
    RoleSpec("campus_manager", "校区负责人", "management"),
    RoleSpec("institution_manager", "机构负责人", "management"),
)

FIRST_NAMES = (
    "赵",
    "钱",
    "孙",
    "李",
    "周",
    "吴",
    "郑",
    "王",
    "冯",
    "陈",
    "刘",
    "杨",
    "黄",
    "林",
    "何",
    "高",
    "郭",
    "马",
    "罗",
    "梁",
    "宋",
    "唐",
    "许",
    "韩",
    "冯",
    "邓",
    "曹",
    "彭",
    "曾",
    "萧",
    "田",
    "董",
    "袁",
    "潘",
    "于",
    "蒋",
    "蔡",
    "余",
    "杜",
    "叶",
    "程",
    "魏",
    "苏",
    "吕",
    "丁",
    "任",
    "沈",
    "姚",
    "卢",
    "姜",
    "崔",
    "钟",
    "谭",
    "陆",
    "汪",
    "范",
    "金",
    "石",
    "廖",
    "贾",
    "夏",
    "韦",
    "傅",
    "方",
    "白",
    "邹",
    "孟",
    "熊",
    "秦",
    "邱",
    "江",
    "尹",
    "薛",
    "闫",
    "段",
    "雷",
    "侯",
    "龙",
    "史",
    "陶",
)

GIVEN_NAMES = (
    "明",
    "华",
    "芳",
    "娜",
    "静",
    "磊",
    "洋",
    "敏",
    "强",
    "丽",
    "杰",
    "婷",
    "宇",
    "欣",
    "晨",
    "然",
    "一",
    "子",
    "梓",
    "思",
    "嘉",
    "佳",
    "雨",
    "雪",
    "梦",
    "诗",
    "书",
    "安",
    "宁",
    "乐",
    "悦",
    "琪",
    "瑶",
    "璐",
    "萱",
    "涵",
    "淼",
    "泽",
    "浩",
    "博",
    "睿",
    "哲",
    "轩",
    "航",
    "辰",
    "昊",
    "皓",
    "凯",
    "骏",
    "峰",
    "川",
    "森",
    "源",
    "远",
    "卓",
    "越",
    "诚",
    "恒",
    "成",
    "毅",
    "清",
    "文",
    "斌",
    "俊",
    "旭",
    "阳",
    "晗",
    "熙",
    "霖",
    "潇",
    "婧",
    "怡",
    "妍",
    "彤",
    "琳",
    "颖",
    "薇",
    "雅",
    "晴",
    "茜",
    "璇",
    "可",
    "楠",
    "宁",
    "之",
    "若",
    "希",
    "知",
    "言",
    "初",
    "亦",
    "南",
    "北",
    "清",
    "遥",
    "墨",
)

SCHOOL_NAMES = (
    "第一中学",
    "实验学校",
    "外国语学校",
    "职业技术学院",
    "信息工程大学",
    "财经大学",
)

INDUSTRIES = ("互联网", "金融", "教育", "制造", "医疗", "传媒", "零售")
JOB_ROLES = ("产品经理", "软件工程师", "运营专员", "数据分析师", "设计师", "销售顾问")
CAREER_STAGES = ("entry", "junior", "middle", "senior")


class Layer1Generator(BaseGenerator):
    layer = 1
    layer_name = "基础维度与组织主数据"

    def __init__(self) -> None:
        self.random = random.Random(int(GENERATION_DEFAULTS["seed"]))
        self.now = self.local_now()
        self.today = self.now.date()
        self.org_window_start = self.now - timedelta(days=1460)
        self.org_window_end = self.now - timedelta(days=180)

    def run(self) -> None:
        self.header()
        self.clear_layer_tables()

        counts = {table: 0 for table in LAYERS[self.layer]["tables"]}
        seed_counts = SeedImporter().import_layer1_seeds()
        counts.update(seed_counts)

        counts["sys_user"] = self.generate_users()
        counts["org_staff_role"] = self.generate_staff_roles()
        counts["staff_profile"] = self.generate_staff_profiles()
        counts["org_institution_manager"] = self.generate_institution_managers()
        counts["org_campus_manager"] = self.generate_campus_managers()
        counts["org_department_manager"] = self.generate_department_managers()
        counts["org_classroom"] = self.generate_classrooms()
        counts["student_profile"] = self.generate_student_profiles()

        self.log_table_counts(counts)
        for check in validate_layer1():
            self.log(f"  [OK] validation: {check}")

    def clear_layer_tables(self) -> None:
        tables = list(reversed(LAYERS[self.layer]["tables"]))
        db.execute("SET FOREIGN_KEY_CHECKS = 0")
        try:
            for table in tables:
                db.execute(f"TRUNCATE TABLE `{table}`")
        finally:
            db.execute("SET FOREIGN_KEY_CHECKS = 1")

    def insert_rows(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        return insert_dict_rows(table_name, rows)

    def build_insert_sql(self, table_name: str, columns: list[str]) -> str:
        return build_insert_sql(table_name, columns)

    def random_datetime(
        self, start: datetime | date, end: datetime | date | None = None
    ) -> datetime:
        if isinstance(start, date) and not isinstance(start, datetime):
            start = datetime.combine(start, datetime.min.time())
        if end is None:
            end = self.now
        elif isinstance(end, date) and not isinstance(end, datetime):
            end = datetime.combine(end, datetime.min.time())
        seconds = max(0, int((end - start).total_seconds()))
        return start + timedelta(seconds=self.random.randint(0, seconds))

    def name(self) -> str:
        return (
            f"{self.random.choice(FIRST_NAMES)}"
            f"{self.random.choice(GIVEN_NAMES)}"
            f"{self.random.choice(GIVEN_NAMES)}"
        )

    def generate_users(self) -> int:
        total = int(GENERATION_DEFAULTS["users"])
        rows: list[dict[str, Any]] = []
        for index in range(1, total + 1):
            created_at = self.random_datetime(
                self.org_window_start, self.org_window_end
            )
            updated_at = self.random_datetime(created_at, self.org_window_end)
            birthday = (
                created_at.date()
                - timedelta(days=self.random.randint(18 * 365, 45 * 365))
            )
            real_name = self.name()
            last_login_at = (
                self.random_datetime(created_at, self.now)
                if self.random.random() < 0.82
                else None
            )
            rows.append(
                {
                    "nickname": f"edu_user_{index:06d}",
                    "real_name": real_name,
                    "mobile": f"139{index:08d}",
                    "email": f"user{index:06d}@edu.example.com",
                    "gender": self.random.choice(("male", "female")),
                    "avatar_url": f"https://cdn.example.com/avatar/{index:06d}.png",
                    "birthday": birthday,
                    "yn": 1,
                    "last_login_at": last_login_at,
                    "created_at": created_at,
                    "updated_at": max(updated_at, last_login_at or updated_at),
                }
            )
        return self.insert_rows("sys_user", rows)

    def generate_staff_roles(self) -> int:
        institutions = self.fetch_institutions()
        rows: list[dict[str, Any]] = []
        for institution in institutions:
            base_time = institution["created_at"]
            for sort_no, spec in enumerate(ROLE_SPECS, start=1):
                created_at = self.random_datetime(base_time, self.org_window_end)
                rows.append(
                    {
                        "institution_id": institution["id"],
                        "role_code": spec.code,
                        "role_name": spec.name,
                        "role_category": spec.category,
                        "sort_no": sort_no * 10,
                        "yn": 1,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.org_window_end
                        ),
                    }
                )
        return self.insert_rows("org_staff_role", rows)

    def generate_staff_profiles(self) -> int:
        campuses = self.fetch_campuses()
        departments = self.fetch_departments()
        roles = self.fetch_staff_roles()
        users = self.fetch_users(limit=self.staff_user_count(campuses))
        user_index = 0
        rows: list[dict[str, Any]] = []

        for campus in campuses:
            campus_departments = [
                dept for dept in departments if dept["campus_id"] == campus["id"]
            ]
            institution_roles = [
                role for role in roles if role["institution_id"] == campus["institution_id"]
            ]
            for local_no in range(int(GENERATION_DEFAULTS["staff_per_campus"])):
                if user_index >= len(users):
                    break
                user = users[user_index]
                user_index += 1
                dept = campus_departments[local_no % len(campus_departments)]
                preferred_category = self.category_for_department(str(dept["dept_name"]))
                role = next(
                    (
                        item
                        for item in institution_roles
                        if item["role_category"] == preferred_category
                    ),
                    institution_roles[local_no % len(institution_roles)],
                )
                created_at = self.random_datetime(
                    max(
                        self.org_window_start,
                        user["created_at"],
                        campus["created_at"],
                        dept["created_at"],
                    ),
                    self.org_window_end,
                )
                rows.append(
                    {
                        "user_id": user["id"],
                        "institution_id": campus["institution_id"],
                        "campus_id": campus["id"],
                        "dept_id": dept["id"],
                        "staff_no": (
                            f"STAFF{campus['institution_id']:03d}"
                            f"{campus['id']:04d}{local_no + 1:03d}"
                        ),
                        "staff_role_id": role["id"],
                        "teacher_intro": (
                            f"{user['real_name']}老师，专注在线教育课程交付。"
                            if role["role_category"] == "teacher"
                            else None
                        ),
                        "yn": 1,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.org_window_end
                        ),
                    }
                )

        return self.insert_rows("staff_profile", rows)

    def generate_institution_managers(self) -> int:
        rows: list[dict[str, Any]] = []
        for institution in self.fetch_institutions():
            staff = self.fetch_staff_for_institution(
                institution["id"], categories=("management", "academic")
            )
            if not staff:
                continue
            selected = staff[0]
            created_at = self.random_datetime(
                max(
                    self.org_window_start,
                    institution["created_at"],
                    selected["created_at"],
                ),
                self.org_window_end,
            )
            rows.append(
                {
                    "institution_id": institution["id"],
                    "staff_id": selected["id"],
                    "yn": 1,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at, self.org_window_end),
                }
            )
        return self.insert_rows("org_institution_manager", rows)

    def generate_campus_managers(self) -> int:
        rows: list[dict[str, Any]] = []
        for campus in self.fetch_campuses():
            staff = self.fetch_staff_for_campus(
                campus["institution_id"], campus["id"], categories=("management", "academic")
            )
            if not staff:
                continue
            selected = staff[0]
            created_at = self.random_datetime(
                max(self.org_window_start, campus["created_at"], selected["created_at"]),
                self.org_window_end,
            )
            rows.append(
                {
                    "campus_id": campus["id"],
                    "staff_id": selected["id"],
                    "yn": 1,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at, self.org_window_end),
                }
            )
        return self.insert_rows("org_campus_manager", rows)

    def generate_department_managers(self) -> int:
        rows: list[dict[str, Any]] = []
        for dept in self.fetch_departments():
            preferred = self.category_for_department(str(dept["dept_name"]))
            staff = self.fetch_staff_for_department(
                dept["institution_id"], dept["campus_id"], dept["id"], preferred
            )
            if not staff:
                continue
            selected = staff[0]
            created_at = self.random_datetime(
                max(self.org_window_start, dept["created_at"], selected["created_at"]),
                self.org_window_end,
            )
            rows.append(
                {
                    "department_id": dept["id"],
                    "staff_id": selected["id"],
                    "yn": 1,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at, self.org_window_end),
                }
            )
        return self.insert_rows("org_department_manager", rows)

    def generate_classrooms(self) -> int:
        rows: list[dict[str, Any]] = []
        institutions = self.fetch_institutions()
        for campus in self.fetch_campuses():
            for index in range(1, 4):
                created_at = self.random_datetime(
                    max(self.org_window_start, campus["created_at"]),
                    self.org_window_end,
                )
                rows.append(
                    {
                        "institution_id": campus["institution_id"],
                        "campus_id": campus["id"],
                        "room_code": f"{campus['campus_code']}_room_{index:02d}",
                        "room_name": f"{campus['campus_name']} {index:02d} 教室",
                        "room_type": "physical",
                        "max_capacity": self.random.choice((24, 30, 36, 48)),
                        "yn": 1,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.org_window_end
                        ),
                    }
                )
        for institution in institutions:
            for index in range(1, 3):
                created_at = self.random_datetime(
                    max(self.org_window_start, institution["created_at"]),
                    self.org_window_end,
                )
                rows.append(
                    {
                        "institution_id": institution["id"],
                        "campus_id": None,
                        "room_code": f"{institution['institution_code']}_live_{index:02d}",
                        "room_name": f"{institution['institution_name']}直播间{index:02d}",
                        "room_type": "live",
                        "max_capacity": self.random.choice((300, 500, 1000, None)),
                        "yn": 1,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.org_window_end
                        ),
                    }
                )
        return self.insert_rows("org_classroom", rows)

    def generate_student_profiles(self) -> int:
        total_users = int(GENERATION_DEFAULTS["users"])
        staff_user_count = self.staff_user_count(self.fetch_campuses())
        student_count = max(0, total_users - staff_user_count)
        users = self.fetch_users(offset=staff_user_count, limit=student_count)
        identities = self.fetch_by_code("dim_learner_identity", "identity_code")
        goals = self.fetch_by_code("dim_learning_goal", "goal_code")
        levels = self.fetch_by_code("dim_education_level", "level_code")
        grades = db.fetch_all(
            "SELECT * FROM dim_grade WHERE grade_type = 'grade' ORDER BY sort_no"
        )
        rows: list[dict[str, Any]] = []

        identity_codes = list(identities)
        k12_goal_codes = ("score_improvement", "school_sync", "exam_preparation")
        adult_goal_codes = (
            "postgraduate_exam",
            "certificate_exam",
            "skill_improvement",
            "job_hunting",
            "promotion",
            "career_switch",
            "interest_learning",
            "other",
        )
        for index, user in enumerate(users, start=1):
            identity_code = self.random.choices(
                identity_codes,
                weights=[45 if code == "in_school_student" else 20 for code in identity_codes],
                k=1,
            )[0]
            is_student = identity_code == "in_school_student"
            goal_code = self.random.choice(k12_goal_codes if is_student else adult_goal_codes)
            created_at = self.random_datetime(
                max(self.org_window_start, user["created_at"]),
                self.org_window_end,
            )
            rows.append(
                {
                    "user_id": user["id"],
                    "learner_identity_id": identities[identity_code]["id"],
                    "learning_goal_id": goals[goal_code]["id"],
                    "education_level_id": None
                    if is_student
                    else levels[self.random.choice(list(levels))]["id"],
                    "grade_id": self.random.choice(grades)["id"] if is_student else None,
                    "school_name": self.random.choice(SCHOOL_NAMES) if is_student else None,
                    "entrance_year": self.random.randint(2018, self.today.year)
                    if is_student
                    else None,
                    "industry_name": None if is_student else self.random.choice(INDUSTRIES),
                    "job_role_name": None if is_student else self.random.choice(JOB_ROLES),
                    "career_stage": None if is_student else self.random.choice(CAREER_STAGES),
                    "years_of_experience": None
                    if is_student
                    else self.random.randint(0, 15),
                    "profile_note": f"Layer1 generated student profile {index}",
                    "yn": 1,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(created_at, self.org_window_end),
                }
            )
        return self.insert_rows("student_profile", rows)

    def staff_user_count(self, campuses: list[dict[str, Any]]) -> int:
        return min(
            int(GENERATION_DEFAULTS["users"]),
            len(campuses) * int(GENERATION_DEFAULTS["staff_per_campus"]),
        )

    def category_for_department(self, dept_name: str) -> str:
        if "教学" in dept_name or "教研" in dept_name:
            return "teacher"
        if "教务" in dept_name:
            return "academic"
        if "销售" in dept_name:
            return "sales"
        if "运营" in dept_name:
            return "operations"
        if "服务" in dept_name or "客服" in dept_name:
            return "service"
        return "management"

    def fetch_institutions(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM org_institution ORDER BY id")

    def fetch_campuses(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM org_campus ORDER BY id")

    def fetch_departments(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM org_department ORDER BY id")

    def fetch_users(self, offset: int = 0, limit: int | None = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM sys_user ORDER BY id"
        if limit is not None:
            sql += f" LIMIT {int(limit)} OFFSET {int(offset)}"
        return db.fetch_all(sql)

    def fetch_staff_roles(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM org_staff_role ORDER BY institution_id, sort_no")

    def fetch_by_code(self, table_name: str, code_column: str) -> dict[str, dict[str, Any]]:
        rows = db.fetch_all(f"SELECT * FROM `{table_name}` ORDER BY id")
        return {str(row[code_column]): row for row in rows}

    def fetch_staff_for_institution(
        self, institution_id: int, categories: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        placeholders = ", ".join(["%s"] * len(categories))
        return db.fetch_all(
            f"""
            SELECT s.*
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE s.institution_id = %s
              AND r.role_category IN ({placeholders})
            ORDER BY s.campus_id IS NOT NULL, s.id
            """,
            (institution_id, *categories),
        )

    def fetch_staff_for_campus(
        self, institution_id: int, campus_id: int, categories: tuple[str, ...]
    ) -> list[dict[str, Any]]:
        placeholders = ", ".join(["%s"] * len(categories))
        return db.fetch_all(
            f"""
            SELECT s.*
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE s.institution_id = %s
              AND s.campus_id = %s
              AND r.role_category IN ({placeholders})
            ORDER BY s.id
            """,
            (institution_id, campus_id, *categories),
        )

    def fetch_staff_for_department(
        self, institution_id: int, campus_id: int, dept_id: int, category: str
    ) -> list[dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT s.*
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE s.institution_id = %s
              AND s.campus_id = %s
              AND s.dept_id = %s
              AND r.role_category = %s
            ORDER BY s.id
            """,
            (institution_id, campus_id, dept_id, category),
        )
        if rows:
            return rows
        return db.fetch_all(
            """
            SELECT s.*
            FROM staff_profile AS s
            WHERE s.institution_id = %s
              AND s.campus_id = %s
              AND s.dept_id = %s
            ORDER BY s.id
            """,
            (institution_id, campus_id, dept_id),
        )
