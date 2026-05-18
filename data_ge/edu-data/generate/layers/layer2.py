"""Layer2: course supply master data."""

from __future__ import annotations

import csv
import json
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from ..config import GENERATION_DEFAULTS, LAYERS, SEEDS_DIR
from ..db import db
from ..insert_support import insert_dict_rows
from .base import BaseGenerator
from .validations import validate_layer2

DELIVERY_MODE_NAMES = {
    "online_live": "直播",
    "online_recorded": "录播",
    "offline_face_to_face": "面授",
}

ASSET_SPECS = (
    ("handout", "pdf", "讲义", "enrolled_only"),
    ("reference", "pdf", "参考资料", "enrolled_only"),
    ("video", "mp4", "回放视频", "enrolled_only"),
)


class Layer2Generator(BaseGenerator):
    layer = 2
    layer_name = "课程供给主数据"

    def __init__(self) -> None:
        self.random = random.Random(int(GENERATION_DEFAULTS["seed"]) + 2)
        self.now = self.local_now()
        self.today = self.now.date()
        self.course_window_start = self.today - timedelta(days=730)
        self.course_window_end = self.today + timedelta(days=90)
        self.series_window_end = self.today
        self.course_window_start_dt = datetime.combine(
            self.course_window_start, datetime.min.time()
        )
        self.series_window_end_dt = datetime.combine(
            self.series_window_end, datetime.min.time()
        ).replace(hour=23, minute=59, second=59)
        self.course_window_end_dt = datetime.combine(
            self.course_window_end, datetime.min.time()
        ).replace(hour=23, minute=59, second=59)

    def normalize_datetime(self, value: datetime | date) -> datetime:
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, datetime.min.time())
        return value

    def created_at_ceiling(self, *candidates: datetime | date) -> datetime:
        normalized = [self.now]
        normalized.extend(self.normalize_datetime(candidate) for candidate in candidates)
        return min(normalized)

    def evenly_distributed_datetime(
        self,
        index: int,
        total: int,
        start: datetime | date,
        end: datetime | date,
        jitter_seconds: int = 0,
    ) -> datetime:
        start_dt = self.normalize_datetime(start)
        end_dt = self.normalize_datetime(end)
        if end_dt < start_dt:
            end_dt = start_dt
        span_seconds = int((end_dt - start_dt).total_seconds())
        if total <= 1 or span_seconds <= 0:
            offset_seconds = span_seconds // 2
        else:
            offset_seconds = round(span_seconds * index / (total - 1))
        if jitter_seconds > 0:
            jitter = self.random.randint(-jitter_seconds, jitter_seconds)
            offset_seconds = max(0, min(span_seconds, offset_seconds + jitter))
        return start_dt + timedelta(seconds=offset_seconds)

    def distributed_date_in_window(
        self,
        start: date,
        end: date,
        key: int,
    ) -> date:
        if end < start:
            end = start
        span_days = max(0, (end - start).days)
        if span_days == 0:
            return start
        offset = key % (span_days + 1)
        return start + timedelta(days=offset)

    def run(self) -> None:
        self.header()
        self.clear_layer_tables()

        counts = {table: 0 for table in LAYERS[self.layer]["tables"]}
        counts["series"] = self.generate_series()
        counts["series_category_rel"] = self.generate_series_category_rel()
        counts["series_cohort"] = self.generate_series_cohorts()
        counts["series_cohort_course"] = self.generate_series_cohort_courses()
        counts["series_cohort_session"] = self.generate_series_cohort_sessions()
        counts["session_teacher_rel"] = self.generate_session_teacher_rels()
        counts["session_asset"] = self.generate_session_assets()
        counts["session_video"] = self.generate_session_videos()
        counts["session_video_chapter"] = self.generate_session_video_chapters()
        counts["session_homework"] = self.generate_session_homeworks()
        counts["session_exam"] = self.generate_session_exams()

        self.log_table_counts(counts)
        for check in validate_layer2():
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

    def load_series_templates(self) -> list[dict[str, Any]]:
        path = SEEDS_DIR / "2_course" / "series.csv"
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))
        limit = int(GENERATION_DEFAULTS["series_template_limit"])
        return rows[:limit] if limit > 0 else rows

    def load_series_course_templates(self) -> dict[str, list[dict[str, Any]]]:
        path = SEEDS_DIR / "2_course" / "series_course.csv"
        with path.open("r", encoding="utf-8", newline="") as file:
            rows = list(csv.DictReader(file))

        templates: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            templates.setdefault(row["series_code"], []).append(
                {
                    "module_code": row["module_code"],
                    "module_name": row["module_name"],
                    "stage_no": int(row["stage_no"]),
                    "lesson_count": int(row["lesson_count"]),
                    "total_hours": int(row["total_hours"]),
                    "module_keywords": row["module_keywords"],
                }
            )
        for items in templates.values():
            items.sort(key=lambda item: item["stage_no"])
        return templates

    def generate_series(self) -> int:
        institutions = self.fetch_institutions()
        creators = self.fetch_staff_users_by_institution(categories=("academic", "management"))
        categories = self.fetch_by_code("dim_course_category", "category_code")
        templates = self.load_series_templates()
        rows: list[dict[str, Any]] = []
        work_items: list[tuple[dict[str, Any], dict[str, str], str, dict[str, Any]]] = []
        for institution in institutions:
            for template in templates:
                category = categories[template["category_level3_code"]]
                for delivery_mode in json.loads(template["delivery_mode_codes"]):
                    work_items.append((institution, template, delivery_mode, category))

        total_items = len(work_items)
        for index, (institution, template, delivery_mode, category) in enumerate(work_items):
            institution_creators = creators[institution["id"]]
            target_created_at = self.evenly_distributed_datetime(
                index=index,
                total=total_items,
                start=self.course_window_start_dt,
                end=self.series_window_end_dt,
                jitter_seconds=3 * 24 * 60 * 60,
            )
            eligible_creators = [
                creator
                for creator in institution_creators
                if creator["created_at"] <= min(
                    self.series_window_end_dt,
                    target_created_at + timedelta(days=15),
                )
            ]
            created_by = self.random.choice(eligible_creators or institution_creators)
            created_floor = max(
                self.course_window_start_dt,
                institution["created_at"],
                created_by["created_at"],
            )
            created_ceiling = min(
                self.series_window_end_dt,
                target_created_at + timedelta(days=15),
            )
            if created_ceiling < created_floor:
                created_ceiling = created_floor
            anchor_floor = max(
                created_floor,
                target_created_at - timedelta(days=15),
            )
            if created_ceiling < anchor_floor:
                anchor_floor = created_floor
            created_at = self.random_datetime(anchor_floor, created_ceiling)
            series_code = f"{template['series_code']}_{delivery_mode}"
            rows.append(
                {
                    "institution_id": institution["id"],
                    "delivery_mode": delivery_mode,
                    "series_code": series_code,
                    "series_name": (
                        f"{template['series_name']}·"
                        f"{DELIVERY_MODE_NAMES[delivery_mode]}"
                    ),
                    "description": (
                        f"{template['product_name']}下的"
                        f"{template['series_name']}课程。"
                    ),
                    "cover_url": (
                        "https://cdn.example.com/course/"
                        f"{template['series_code']}.jpg"
                    ),
                    "target_learner_identity_codes": json.dumps(
                        json.loads(template["target_learner_identity_codes"]),
                        ensure_ascii=False,
                    ),
                    "target_learning_goal_codes": json.dumps(
                        json.loads(template["target_learning_goal_codes"]),
                        ensure_ascii=False,
                    ),
                    "target_grade_codes": json.dumps(
                        json.loads(template["target_grade_codes"]),
                        ensure_ascii=False,
                    ),
                    "sale_status": template["sale_status_code"],
                    "created_by": created_by["user_id"],
                    "created_at": created_at,
                    "updated_at": self.random_datetime(
                        created_at, self.series_window_end_dt
                    ),
                }
            )
            category["_used_by_series_code"] = category["category_code"]
        return self.insert_rows("series", rows)

    def generate_series_category_rel(self) -> int:
        templates = {
            (f"{row['series_code']}_{mode}", mode): row
            for row in self.load_series_templates()
            for mode in json.loads(row["delivery_mode_codes"])
        }
        categories = self.fetch_by_code("dim_course_category", "category_code")
        series_rows = self.fetch_series()
        rows: list[dict[str, Any]] = []
        for series in series_rows:
            template_key = (series["series_code"], series["delivery_mode"])
            template = templates[template_key]
            category = categories[template["category_level3_code"]]
            created_at = self.random_datetime(
                series["created_at"], self.created_at_ceiling(self.series_window_end_dt)
            )
            rows.append(
                {
                    "series_id": series["id"],
                    "category_id": category["id"],
                    "sort_no": 10,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(
                        created_at, self.series_window_end_dt
                    ),
                }
            )
        return self.insert_rows("series_category_rel", rows)

    def generate_series_cohorts(self) -> int:
        campuses = self.fetch_campuses_by_institution()
        head_teachers = self.fetch_staff_by_institution_and_campus(categories=("academic",))
        institution_head_teachers = self.fetch_staff_by_institution(categories=("academic",))
        series_rows = self.fetch_series()
        cohorts_per_series = int(GENERATION_DEFAULTS["cohorts_per_series"])
        rows: list[dict[str, Any]] = []

        for series in series_rows:
            institution_campuses = campuses[series["institution_id"]]
            for index in range(1, cohorts_per_series + 1):
                campus = None
                if series["delivery_mode"] == "offline_face_to_face":
                    campus = institution_campuses[
                        (series["id"] + index) % len(institution_campuses)
                    ]
                    teachers = head_teachers[(series["institution_id"], campus["id"])]
                else:
                    teachers = institution_head_teachers[series["institution_id"]]
                head_teacher = teachers[(series["id"] + index) % len(teachers)]
                open_date = self.cohort_open_date(series["id"], index, cohorts_per_series)
                min_open_date = (
                    max(
                        series["created_at"],
                        head_teacher["created_at"],
                        campus["created_at"] if campus is not None else series["created_at"],
                    ).date()
                    + timedelta(days=1)
                )
                if open_date < min_open_date:
                    open_date = min_open_date + timedelta(days=(index - 1) * 14)
                end_date = (
                    None
                    if series["delivery_mode"] == "online_recorded"
                    else open_date + timedelta(days=55)
                )
                created_at = self.random_datetime(
                    max(
                        series["created_at"],
                        head_teacher["created_at"],
                        campus["created_at"] if campus is not None else series["created_at"],
                    ),
                    self.created_at_ceiling(datetime.combine(open_date, time(hour=8))),
                )
                rows.append(
                    {
                        "institution_id": series["institution_id"],
                        "series_id": series["id"],
                        "campus_id": campus["id"] if campus is not None else None,
                        "head_teacher_id": head_teacher["id"],
                        "cohort_code": f"COH{series['id']:06d}{index:02d}",
                        "cohort_name": (
                            f"{series['series_name']} "
                            f"{open_date.strftime('%Y%m')}期"
                        ),
                        "sale_price": self.cohort_sale_price(
                            series["delivery_mode"],
                            series["id"],
                            index,
                        ),
                        "max_student_count": self.random.choice((30, 40, 50, 60)),
                        "current_student_count": 0,
                        "yn": 1,
                        "start_date": open_date,
                        "end_date": end_date,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.course_window_end_dt
                        ),
                    }
                )
        return self.insert_rows("series_cohort", rows)

    def cohort_sale_price(
        self,
        delivery_mode: str,
        series_id: int,
        index: int,
    ) -> Decimal:
        if delivery_mode == "online_recorded":
            candidates = (Decimal("1999.00"), Decimal("2499.00"), Decimal("2999.00"))
        elif delivery_mode == "online_live":
            candidates = (Decimal("2999.00"), Decimal("3999.00"), Decimal("4999.00"))
        else:
            candidates = (Decimal("3999.00"), Decimal("4999.00"), Decimal("5999.00"))
        return candidates[(series_id + index) % len(candidates)]

    def generate_series_cohort_courses(self) -> int:
        cohorts = self.fetch_cohorts()
        templates_by_series = self.load_series_course_templates()
        fallback_count = int(GENERATION_DEFAULTS["courses_per_cohort"])
        rows: list[dict[str, Any]] = []
        for cohort in cohorts:
            base_series_code = cohort["series_code"]
            for suffix in ("_online_live", "_online_recorded", "_offline_face_to_face"):
                if base_series_code.endswith(suffix):
                    base_series_code = base_series_code[: -len(suffix)]
                    break
            course_templates = templates_by_series.get(base_series_code, [])
            if not course_templates:
                course_templates = [
                    {
                        "module_code": f"MOD{index:02d}",
                        "module_name": f"阶段{index}",
                        "stage_no": index,
                        "lesson_count": int(GENERATION_DEFAULTS["sessions_per_course"]),
                        "total_hours": int(GENERATION_DEFAULTS["sessions_per_course"]) * 2,
                        "module_keywords": "[]",
                    }
                    for index in range(1, fallback_count + 1)
                ]
            cohort_end_date = cohort["end_date"] or cohort["start_date"] + timedelta(days=55)
            total_days = max(1, (cohort_end_date - cohort["start_date"]).days + 1)
            module_count = len(course_templates)
            module_days = max(1, total_days // module_count)
            for index, template in enumerate(course_templates, start=1):
                start_date = cohort["start_date"] + timedelta(days=(index - 1) * module_days)
                end_date = (
                    cohort_end_date
                    if index == module_count
                    else start_date + timedelta(days=module_days - 1)
                )
                created_at = self.random_datetime(
                    cohort["created_at"],
                    self.created_at_ceiling(datetime.combine(start_date, time(hour=8))),
                )
                rows.append(
                    {
                        "cohort_id": cohort["id"],
                        "module_code": template["module_code"],
                        "module_name": template["module_name"],
                        "description": (
                            f"{cohort['cohort_name']}·{template['module_name']}。"
                        ),
                        "lesson_count": template["lesson_count"],
                        "total_hours": template["total_hours"],
                        "stage_no": template["stage_no"],
                        "start_date": start_date,
                        "end_date": end_date,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.course_window_end_dt
                        ),
                    }
                )
        return self.insert_rows("series_cohort_course", rows)

    def generate_series_cohort_sessions(self) -> int:
        courses = self.fetch_cohort_courses()
        rooms = self.fetch_rooms_by_institution_and_type()
        rows: list[dict[str, Any]] = []

        for course in courses:
            delivery_mode = course["delivery_mode"]
            session_dates = self.session_dates(
                course["start_date"], course["end_date"], course["lesson_count"]
            )
            for index, teaching_date in enumerate(session_dates, start=1):
                room_id = None
                if delivery_mode == "offline_face_to_face":
                    room_id = self.pick_room(
                        rooms,
                        course["institution_id"],
                        "physical",
                        campus_id=course["campus_id"],
                    )
                elif delivery_mode == "online_live":
                    room_id = self.pick_room(rooms, course["institution_id"], "live")
                created_at = self.random_datetime(
                    course["created_at"],
                    self.created_at_ceiling(datetime.combine(teaching_date, time(hour=8))),
                )
                rows.append(
                    {
                        "series_cohort_course_id": course["id"],
                        "room_id": room_id,
                        "session_no": index,
                        "session_title": f"{course['module_name']} 第{index}课",
                        "teaching_status": self.teaching_status(teaching_date),
                        "checkin_required": 1 if delivery_mode != "online_recorded" else 0,
                        "teaching_date": teaching_date,
                        "start_time": (
                            None
                            if delivery_mode == "online_recorded"
                            else time(hour=19, minute=0)
                        ),
                        "end_time": (
                            None
                            if delivery_mode == "online_recorded"
                            else time(hour=21, minute=0)
                        ),
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.course_window_end_dt
                        ),
                    }
                )
        return self.insert_rows("series_cohort_session", rows)

    def generate_session_teacher_rels(self) -> int:
        sessions = self.fetch_sessions_with_context()
        teachers = self.fetch_staff_by_institution(categories=("teacher",))
        rows: list[dict[str, Any]] = []
        for session in sessions:
            institution_teachers = teachers[session["institution_id"]]
            teacher = institution_teachers[session["id"] % len(institution_teachers)]
            created_at = self.random_datetime(
                max(session["created_at"], teacher["created_at"]),
                self.created_at_ceiling(self.course_window_end_dt),
            )
            rows.append(
                {
                    "session_id": session["id"],
                    "teacher_id": teacher["id"],
                    "sort_no": 10,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(
                        created_at, self.course_window_end_dt
                    ),
                }
            )
        return self.insert_rows("session_teacher_rel", rows)

    def generate_session_assets(self) -> int:
        sessions = self.fetch_sessions_with_context()
        uploaders = self.fetch_staff_users_by_institution(categories=("teacher", "academic"))
        rows: list[dict[str, Any]] = []
        for session in sessions:
            institution_uploaders = uploaders[session["institution_id"]]
            uploader = institution_uploaders[session["id"] % len(institution_uploaders)]
            for index, (category, file_type, label, access_scope) in enumerate(
                ASSET_SPECS, start=1
            ):
                created_at = self.random_datetime(
                    max(session["created_at"], uploader["created_at"]),
                    self.created_at_ceiling(self.course_window_end_dt),
                )
                rows.append(
                    {
                        "session_id": session["id"],
                        "asset_code": f"AST{session['id']:08d}{index:02d}",
                        "asset_name": f"{session['session_title']} {label}",
                        "file_type": file_type,
                        "material_category": category,
                        "sort_no": index * 10,
                        "access_scope": access_scope,
                        "file_url": (
                            "https://cdn.example.com/session-assets/"
                            f"{session['id']:08d}_{index:02d}.{file_type}"
                        ),
                        "file_size": self.random.randint(512_000, 800_000_000),
                        "uploader_user_id": uploader["user_id"],
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.course_window_end_dt
                        ),
                    }
                )
        return self.insert_rows("session_asset", rows)

    def generate_session_videos(self) -> int:
        assets = db.fetch_all(
            """
            SELECT *
            FROM session_asset
            WHERE material_category = 'video'
            ORDER BY id
            """
        )
        rows: list[dict[str, Any]] = []
        for asset in assets:
            created_at = self.random_datetime(
                asset["created_at"], self.created_at_ceiling(self.course_window_end_dt)
            )
            rows.append(
                {
                    "asset_id": asset["id"],
                    "video_code": f"VID{asset['id']:08d}",
                    "video_title": asset["asset_name"],
                    "cover_url": f"https://cdn.example.com/video-cover/{asset['id']:08d}.jpg",
                    "duration_seconds": self.random.randint(3600, 7200),
                    "resolution_label": self.random.choice(("720p", "1080p")),
                    "bitrate_kbps": self.random.choice((1200, 1800, 2400, 3200)),
                    "transcode_status": "completed",
                    "review_status": "approved",
                    "created_at": created_at,
                    "updated_at": self.random_datetime(
                        created_at, self.course_window_end_dt
                    ),
                }
            )
        return self.insert_rows("session_video", rows)

    def generate_session_video_chapters(self) -> int:
        videos = db.fetch_all("SELECT * FROM session_video ORDER BY id")
        rows: list[dict[str, Any]] = []
        for video in videos:
            chapter_count = 3
            step = video["duration_seconds"] // chapter_count
            for index in range(1, chapter_count + 1):
                start_second = (index - 1) * step
                end_second = (
                    video["duration_seconds"] if index == chapter_count else index * step
                )
                created_at = self.random_datetime(
                    video["created_at"], self.created_at_ceiling(self.course_window_end_dt)
                )
                rows.append(
                    {
                        "video_id": video["id"],
                        "chapter_no": index,
                        "chapter_title": f"第{index}章",
                        "start_second": start_second,
                        "end_second": end_second,
                        "created_at": created_at,
                        "updated_at": self.random_datetime(
                            created_at, self.course_window_end_dt
                        ),
                    }
                )
        return self.insert_rows("session_video_chapter", rows)

    def generate_session_homeworks(self) -> int:
        sessions = self.fetch_sessions_with_context()
        teachers = self.fetch_staff_by_institution(categories=("teacher",))
        rows: list[dict[str, Any]] = []
        for session in sessions:
            if session["delivery_mode"] == "online_recorded":
                continue
            if session["session_no"] % 2 != 0:
                continue
            teacher = teachers[session["institution_id"]][
                session["id"] % len(teachers[session["institution_id"]])
            ]
            due_at = datetime.combine(session["teaching_date"], time(hour=23, minute=59)) + timedelta(
                days=7
            )
            min_created_at = max(session["created_at"], teacher["created_at"])
            if due_at <= min_created_at:
                due_at = min_created_at + timedelta(days=7)
            created_at = self.random_datetime(
                min_created_at,
                self.created_at_ceiling(due_at - timedelta(hours=1)),
            )
            rows.append(
                {
                    "session_id": session["id"],
                    "homework_code": f"HW{session['id']:08d}",
                    "homework_name": f"{session['session_title']} 作业",
                    "created_by": teacher["id"],
                    "due_at": due_at,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(
                        created_at, self.course_window_end_dt
                    ),
                }
            )
        return self.insert_rows("session_homework", rows)

    def generate_session_exams(self) -> int:
        sessions = self.fetch_last_sessions_by_course()
        teachers = self.fetch_staff_by_institution(categories=("teacher",))
        rows: list[dict[str, Any]] = []
        for session in sessions:
            if session["delivery_mode"] == "online_recorded":
                continue
            teacher = teachers[session["institution_id"]][
                session["id"] % len(teachers[session["institution_id"]])
            ]
            min_created_at = max(session["created_at"], teacher["created_at"])
            window_start_at = datetime.combine(
                session["teaching_date"], time(hour=9)
            ) + timedelta(days=1)
            if window_start_at <= min_created_at:
                window_start_at = min_created_at + timedelta(hours=2)
            deadline_at = window_start_at + timedelta(days=7)
            created_at = self.random_datetime(
                min_created_at,
                self.created_at_ceiling(window_start_at - timedelta(hours=1)),
            )
            publish_at = created_at + timedelta(hours=1)
            rows.append(
                {
                    "session_id": session["id"],
                    "exam_code": f"EXAM{session['id']:08d}",
                    "exam_name": f"{session['session_title']} 测验",
                    "total_score": 100,
                    "pass_score": 60,
                    "publish_status": "published",
                    "created_by": teacher["id"],
                    "duration_minutes": 90,
                    "window_start_at": window_start_at,
                    "deadline_at": deadline_at,
                    "publish_at": publish_at,
                    "created_at": created_at,
                    "updated_at": self.random_datetime(
                        publish_at, self.course_window_end_dt
                    ),
                }
            )
        return self.insert_rows("session_exam", rows)

    def cohort_open_date(self, series_id: int, index: int, total: int) -> date:
        history_end = self.today - timedelta(days=45)
        current_start = self.today - timedelta(days=44)
        current_end = self.today + timedelta(days=30)
        future_start = self.today + timedelta(days=31)
        windows = [
            (self.course_window_start, max(self.course_window_start, history_end)),
            (
                max(self.course_window_start, current_start),
                min(self.course_window_end, current_end),
            ),
            (min(self.course_window_end, future_start), self.course_window_end),
        ]
        valid_windows = [window for window in windows if window[0] <= window[1]]
        if not valid_windows:
            return self.today

        window_count = len(valid_windows)
        window_index = min(window_count - 1, ((index - 1) * window_count) // max(total, 1))
        slot_start, slot_end = valid_windows[window_index]
        distribution_key = series_id * 131 + index * 29
        return self.distributed_date_in_window(slot_start, slot_end, distribution_key)

    def session_dates(self, start_date: date, end_date: date, count: int) -> list[date]:
        if count == 1:
            return [start_date]
        total_days = max(1, (end_date - start_date).days)
        return [
            start_date + timedelta(days=round(total_days * index / (count - 1)))
            for index in range(count)
        ]

    def teaching_status(self, teaching_date: date) -> str:
        if teaching_date > self.today:
            return "scheduled"
        if teaching_date == self.today:
            return "in_progress"
        return "completed"

    def pick_room(
        self,
        rooms: dict[tuple[int, str], list[dict[str, Any]]],
        institution_id: int,
        room_type: str,
        campus_id: int | None = None,
    ) -> int:
        candidates = rooms[(institution_id, room_type)]
        if campus_id is not None:
            campus_candidates = [room for room in candidates if room["campus_id"] == campus_id]
            if campus_candidates:
                candidates = campus_candidates
        return candidates[self.random.randrange(len(candidates))]["id"]

    def fetch_institutions(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM org_institution ORDER BY id")

    def fetch_series(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM series ORDER BY id")

    def fetch_cohorts(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                c.*,
                s.series_code
            FROM series_cohort AS c
            JOIN series AS s ON s.id = c.series_id
            ORDER BY c.id
            """
        )

    def fetch_cohort_courses(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                cc.*,
                c.institution_id,
                c.campus_id,
                s.delivery_mode
            FROM series_cohort_course AS cc
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN series AS s ON s.id = c.series_id
            ORDER BY cc.id
            """
        )

    def fetch_sessions_with_context(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                ss.*,
                c.institution_id,
                c.campus_id,
                s.delivery_mode
            FROM series_cohort_session AS ss
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS c ON c.id = cc.cohort_id
            JOIN series AS s ON s.id = c.series_id
            ORDER BY ss.id
            """
        )

    def fetch_last_sessions_by_course(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT session_with_context.*
            FROM (
                SELECT
                    ss.*,
                    c.institution_id,
                    c.campus_id,
                    s.delivery_mode
                FROM series_cohort_session AS ss
                JOIN series_cohort_course AS cc
                    ON cc.id = ss.series_cohort_course_id
                JOIN series_cohort AS c ON c.id = cc.cohort_id
                JOIN series AS s ON s.id = c.series_id
            ) AS session_with_context
            JOIN (
                SELECT
                    series_cohort_course_id,
                    MAX(session_no) AS max_session_no
                FROM series_cohort_session
                GROUP BY series_cohort_course_id
            ) AS last_session
                ON last_session.series_cohort_course_id
                    = session_with_context.series_cohort_course_id
                AND last_session.max_session_no = session_with_context.session_no
            ORDER BY session_with_context.id
            """
        )

    def fetch_by_code(self, table_name: str, code_column: str) -> dict[str, dict[str, Any]]:
        rows = db.fetch_all(f"SELECT * FROM `{table_name}` ORDER BY id")
        return {str(row[code_column]): row for row in rows}

    def fetch_campuses_by_institution(self) -> dict[int, list[dict[str, Any]]]:
        rows = db.fetch_all("SELECT * FROM org_campus ORDER BY institution_id, id")
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["institution_id"], []).append(row)
        return result

    def fetch_staff_by_institution(
        self, categories: tuple[str, ...]
    ) -> dict[int, list[dict[str, Any]]]:
        placeholders = ", ".join(["%s"] * len(categories))
        rows = db.fetch_all(
            f"""
            SELECT s.*, r.role_category
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE r.role_category IN ({placeholders})
            ORDER BY s.institution_id, s.id
            """,
            categories,
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["institution_id"], []).append(row)
        return result

    def fetch_staff_users_by_institution(
        self, categories: tuple[str, ...]
    ) -> dict[int, list[dict[str, Any]]]:
        placeholders = ", ".join(["%s"] * len(categories))
        rows = db.fetch_all(
            f"""
            SELECT
                s.*,
                u.created_at AS user_created_at
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            JOIN sys_user AS u ON u.id = s.user_id
            WHERE r.role_category IN ({placeholders})
            ORDER BY s.institution_id, s.id
            """,
            categories,
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["institution_id"], []).append(row)
        return result

    def fetch_staff_by_institution_and_campus(
        self, categories: tuple[str, ...]
    ) -> dict[tuple[int, int], list[dict[str, Any]]]:
        placeholders = ", ".join(["%s"] * len(categories))
        rows = db.fetch_all(
            f"""
            SELECT s.*, r.role_category
            FROM staff_profile AS s
            JOIN org_staff_role AS r ON r.id = s.staff_role_id
            WHERE s.campus_id IS NOT NULL
              AND r.role_category IN ({placeholders})
            ORDER BY s.institution_id, s.campus_id, s.id
            """,
            categories,
        )
        result: dict[tuple[int, int], list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault((row["institution_id"], row["campus_id"]), []).append(row)
        return result

    def fetch_rooms_by_institution_and_type(
        self,
    ) -> dict[tuple[int, str], list[dict[str, Any]]]:
        rows = db.fetch_all("SELECT * FROM org_classroom ORDER BY institution_id, id")
        result: dict[tuple[int, str], list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault((row["institution_id"], row["room_type"]), []).append(row)
        return result
