"""Layer5: learning, interaction, and service process data."""

from __future__ import annotations

import json
import random
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from ..config import GENERATION_DEFAULTS, LAYERS
from ..db import db
from ..insert_support import insert_dict_rows
from .base import BaseGenerator
from .validations import validate_layer5

ATTENDANCE_STATUSES = ("present", "late", "leave", "absent")
LEAVE_TYPES = ("sick_leave", "personal_leave", "school_activity")
DEVICE_TYPES = ("mobile", "tablet", "desktop")
CLIENT_TYPES = ("app", "h5", "pc_web", "mini_program")
DEVICE_OS_BY_CLIENT = {
    "app": ("ios", "android", "harmonyos"),
    "h5": ("ios", "android", "windows", "macos"),
    "pc_web": ("windows", "macos", "linux"),
    "mini_program": ("ios", "android"),
}
EXIT_REASONS = ("manual_exit", "play_complete", "network_interrupt", "app_background")
NETWORK_TYPES = ("wifi", "mobile_5g", "mobile_4g", "ethernet", "unknown")
PLAYBACK_RATES = (Decimal("1.00"), Decimal("1.25"), Decimal("1.50"), Decimal("2.00"))
TOPIC_TITLES = (
    "这节课的重点大家是怎么理解的？",
    "作业里最难的一题你是怎么做的？",
    "这个模块有什么推荐的复习方法？",
    "老师讲的案例我想再展开讨论一下。",
    "这节课有哪些知识点最容易混淆？",
    "大家觉得这次课后练习难度怎么样？",
    "这一模块如果要复习，大家会先从哪里开始？",
    "老师这节课提到的方法在实际中好用吗？",
    "有没有同学整理了这节课的思维导图？",
    "这个知识点和上一模块之间的联系怎么理解？",
    "今天课上的例题有没有更简单的解法？",
    "如果是零基础，大家觉得这部分应该怎么学？",
    "这节课的重点内容适合怎么做笔记？",
    "作业里的开放题大家都怎么组织答案的？",
    "老师强调的高频考点大家总结出来了吗？",
    "这部分内容适合通过刷题还是看案例来巩固？",
    "今天课程里哪个部分你觉得最有收获？",
    "如果把这节课内容讲给别人听，你会怎么讲？",
    "有没有同学在做题时踩过这部分的坑？",
    "这节课讲的方法和你之前的做法有什么差别？",
    "这里的概念边界大家是怎么区分的？",
    "如果下次复盘这节课，你最想先复盘哪一块？",
    "大家觉得这一讲和实际项目/考试的关联大吗？",
    "这一模块有没有推荐的补充资料或练习方法？",
)
TOPIC_CONTENTS = (
    "我觉得这节课的信息量挺大，想听听大家对重点知识点的梳理。",
    "作业里有一题卡了很久，欢迎一起交流思路。",
    "最近在复习这个模块，想看看大家有没有更高效的方法。",
    "老师提到的案例很有意思，想继续讨论它在实际场景里的应用。",
    "这节课有几个知识点看起来很像，我有点分不清，想听听大家是怎么记忆和区分的。",
    "课后自己复盘了一下，发现有些细节还没完全吃透，想和大家一起整理重点。",
    "这次练习里有几道题和课堂内容联系很强，欢迎大家聊聊自己的解题路径。",
    "老师课上提到的方法我觉得挺实用，但还想知道大家在真实场景里会怎么用。",
    "我在整理笔记的时候发现这一讲特别适合串联前后知识点，想看看大家有没有自己的结构化方法。",
    "这部分内容如果只听课感觉还不够，想请大家推荐一下更适合巩固的练习方式。",
    "今天听完之后整体理解比之前清晰了不少，但还是有几个细节想和大家确认一下。",
    "做题时发现自己容易在同一个地方出错，想看看大家有没有类似情况和改进方法。",
    "我觉得这一模块很适合做一次专题复盘，欢迎大家一起补充常见易错点。",
    "老师举的案例挺贴近实际，我想继续聊聊这个案例背后的思路和迁移方法。",
    "这部分内容如果放到考试/项目里，大家觉得最容易考或最容易用到的是哪一块？",
    "自己尝试总结了一版框架，但不知道有没有遗漏，想听听大家的补充意见。",
    "我发现这节课内容和前面某一讲联系特别紧密，欢迎大家一起梳理这条知识链路。",
    "这次练习里最让我卡住的不是计算，而是理解题意，想看看大家是怎么拆题的。",
    "如果把这节课内容讲给一个没学过的人听，应该先讲哪几个核心概念？",
    "我对老师课上强调的几个边界条件还不是特别稳，想和大家一起对一下理解。",
    "今天课后回看了一遍笔记，感觉可以再提炼出一份更适合考前复习的版本。",
    "这部分知识点如果靠死记容易忘，我想看看大家有没有更好的理解型学习方法。",
    "我试着把今天内容画成结构图，发现还有空白区域，欢迎大家一起补全。",
    "课程内容本身不难，但放到题目里就有点绕，想听听大家如何把知识点和题型对应起来。",
)
POST_CONTENTS = (
    "我觉得这个点可以从课件第三部分再看一遍。",
    "老师上课举的例子其实已经把关键区别讲得很清楚了。",
    "我这边是先拆步骤，再去对照题干要求。",
    "这个问题我也遇到过，后来是通过多做一题理解的。",
    "我当时也是在这里卡住，后来重新整理了一下概念边界就顺了很多。",
    "这块如果结合老师的板书一起看，会比只看讲义更容易理解。",
    "我自己的方法是先列出关键词，再看它们之间的关系。",
    "这题我一开始也想复杂了，后来发现核心就是抓住题干里的限定条件。",
    "我觉得可以先把例题完整走一遍，再回来看知识点定义。",
    "这一部分特别适合自己复述一遍，复述的时候很容易发现哪里没懂。",
    "我做笔记的时候把它和上一讲放在一起对照，看起来会更清楚。",
    "如果从应用场景倒推，其实这个知识点就没那么抽象了。",
    "我后来是通过再做两道同类型题把这个点补上的。",
    "老师课上提到的那个反例我觉得特别有帮助，能一下子看出区别。",
    "可以先不要急着做题，先把判断依据列清楚再下手。",
    "这部分我觉得最重要的是先区分主干思路和细节步骤。",
    "我自己理解的时候会先问一句：这一步到底是在解决什么问题。",
    "如果把这几个概念拆成表格对比，记忆成本会低很多。",
    "我感觉课件里的图示已经很关键了，建议结合图示再复盘一次。",
    "这题其实不是难在算，而是难在第一步怎么切进去。",
    "我后来发现自己不是不会做，而是对题目条件敏感度不够。",
    "老师讲的那个案例和这道题本质上是同一类，迁移一下就通了。",
    "我建议先看答案结构，再回头分析每一步为什么这么写。",
    "这块我用错题本单独记了一页，后面复习时很有用。",
)
REVIEW_TAG_POOL = (
    "讲解清晰",
    "内容扎实",
    "服务及时",
    "练习充足",
    "节奏合适",
    "案例实用",
    "重点明确",
    "互动充分",
    "答疑细致",
    "方法实用",
    "逻辑清楚",
    "资料完整",
    "反馈及时",
    "课堂氛围好",
    "干货很多",
    "条理分明",
    "复习高效",
    "收获很大",
    "讲练结合",
    "启发性强",
)
SERVICE_TICKET_TYPES = ("after_sales", "complaint", "refund")
SERVICE_TICKET_SOURCES = ("user_app", "customer_service", "system_auto", "admin_manual")
PRIORITY_LEVELS = ("low", "medium", "high", "urgent")
FOLLOW_TYPES = ("reply_user", "status_update", "refund_review", "internal_note", "escalation")
FOLLOW_CHANNELS = ("phone", "user_app", "sms", "wechat", "internal_system", "offline")
FOLLOW_RESULTS = (
    "pending_follow_up",
    "user_confirmed",
    "user_unreachable",
    "resolved",
    "escalated",
)
OPEN_FOLLOW_RESULTS = tuple(result for result in FOLLOW_RESULTS if result != "resolved")


class Layer5Generator(BaseGenerator):
    layer = 5
    layer_name = "学习、互动与服务过程"

    def __init__(self) -> None:
        self.random = random.Random(int(GENERATION_DEFAULTS["seed"]) + 5)
        self.now = self.local_now()
        self.today = self.now.date()

    def run(self) -> None:
        self.header()
        self.clear_layer_tables()

        counts = {table: 0 for table in LAYERS[self.layer]["tables"]}
        counts["session_attendance"] = self.generate_attendance()
        counts["session_video_play"] = self.generate_video_play()
        counts["session_video_play_event"] = self.generate_video_play_events()
        counts["session_homework_submission"] = self.generate_homework_submissions()
        counts["session_exam_submission"] = self.generate_exam_submissions()
        counts["cohort_discussion_topic"] = self.generate_discussion_topics()
        counts["cohort_discussion_post"] = self.generate_discussion_posts()
        self.refresh_discussion_stats()
        counts["cohort_review"] = self.generate_cohort_reviews()
        counts["service_ticket"] = self.generate_service_tickets()
        counts["service_ticket_follow_record"] = self.generate_service_ticket_follow_records()
        self.refresh_ticket_stats()
        counts["service_ticket_satisfaction_survey"] = (
            self.generate_service_ticket_satisfaction_surveys()
        )

        self.log_table_counts(counts)
        for check in validate_layer5(self.now):
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
        if end < start:
            end = start
        seconds = max(0, int((end - start).total_seconds()))
        return start + timedelta(seconds=self.random.randint(0, seconds))

    def cap_at_now(self, value: datetime) -> datetime:
        return min(value, self.now)

    def normalize_sql_time(self, value: time | timedelta) -> time:
        if isinstance(value, time):
            return value
        total_seconds = int(value.total_seconds()) % (24 * 60 * 60)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return time(hour=hours, minute=minutes, second=seconds)

    def generate_attendance(self) -> int:
        rows: list[dict[str, Any]] = []
        sessions = self.fetch_teachable_sessions()
        fulfillments = self.fetch_effective_fulfillments_by_cohort()
        for session in sessions:
            for rel in fulfillments.get(session["cohort_id"], []):
                created_at = max(session["created_at"], rel["created_at"])
                status = self.pick_attendance_status()
                checkin_time = None
                leave_type = None
                remark = None
                session_start_time = self.normalize_sql_time(session["start_time"])
                session_end_time = self.normalize_sql_time(session["end_time"])
                if status in {"present", "late"}:
                    base_time = datetime.combine(session["teaching_date"], session_start_time)
                    offset = self.random.randint(0, 25) if status == "late" else self.random.randint(-5, 8)
                    checkin_time = max(created_at, base_time + timedelta(minutes=offset))
                elif status == "leave":
                    leave_type = self.random.choice(LEAVE_TYPES)
                    remark = "学员已提前请假。"
                created_end = datetime.combine(session["teaching_date"], session_end_time)
                if checkin_time is not None:
                    created_end = min(created_end, checkin_time)
                created_dt = self.random_datetime(
                    created_at,
                    created_end,
                )
                updated_at = max(created_dt, checkin_time or created_dt)
                rows.append(
                    {
                        "institution_id": session["institution_id"],
                        "session_id": session["id"],
                        "cohort_id": session["cohort_id"],
                        "user_id": rel["user_id"],
                        "student_id": rel["student_id"],
                        "attendance_status": status,
                        "leave_type": leave_type,
                        "remark": remark,
                        "checkin_time": checkin_time,
                        "created_at": created_dt,
                        "updated_at": updated_at,
                    }
                )
        return self.insert_rows("session_attendance", rows)

    def generate_video_play(self) -> int:
        ratio = float(GENERATION_DEFAULTS["video_play_ratio"])
        rows: list[dict[str, Any]] = []
        videos = self.fetch_videos_with_context()
        fulfillments = self.fetch_effective_fulfillments_by_cohort()
        sequence = 1
        for video in videos:
            for rel in fulfillments.get(video["cohort_id"], []):
                if self.random.random() > ratio:
                    continue
                created_at = max(video["created_at"], rel["created_at"])
                client_type = self.random.choice(CLIENT_TYPES)
                device_os = self.random.choice(DEVICE_OS_BY_CLIENT[client_type])
                duration = video["duration_seconds"]
                completed = self.random.random() < 0.55
                progress_percent = Decimal("100.00") if completed else Decimal(str(self.random.randint(8, 96)))
                last_position_seconds = (
                    duration
                    if completed
                    else max(1, int(duration * float(progress_percent) / 100))
                )
                watched_seconds = max(
                    30,
                    last_position_seconds - self.random.randint(0, max(1, last_position_seconds // 5)),
                )
                started_at = self.random_datetime(created_at, self.now - timedelta(minutes=1))
                ended_at = self.cap_at_now(
                    started_at + timedelta(seconds=min(duration, watched_seconds + self.random.randint(0, 180)))
                )
                if not completed and self.random.random() < 0.25:
                    ended_at = None
                updated_at = max(started_at, ended_at or started_at)
                rows.append(
                    {
                        "institution_id": video["institution_id"],
                        "video_id": video["id"],
                        "user_id": rel["user_id"],
                        "student_id": rel["student_id"],
                        "play_session_no": f"PLAY{sequence:012d}",
                        "device_type": self.random.choice(DEVICE_TYPES),
                        "client_type": client_type,
                        "device_os": device_os,
                        "last_position_seconds": last_position_seconds,
                        "progress_percent": progress_percent,
                        "completed_flag": 1 if completed else 0,
                        "exit_reason": "play_complete" if completed else self.random.choice(EXIT_REASONS),
                        "watched_seconds": watched_seconds,
                        "started_at": started_at,
                        "ended_at": ended_at,
                        "created_at": started_at,
                        "updated_at": updated_at,
                    }
                )
                sequence += 1
        return self.insert_rows("session_video_play", rows)

    def generate_video_play_events(self) -> int:
        rows: list[dict[str, Any]] = []
        play_rows = self.fetch_video_play_with_duration()
        for play in play_rows:
            events = [
                ("play", 0, play["started_at"]),
            ]
            if play["completed_flag"] == 1:
                pause_pos = max(1, int(play["last_position_seconds"] * 0.35))
                resume_pos = max(pause_pos, int(play["last_position_seconds"] * 0.36))
                complete_time = play["ended_at"] or play["updated_at"]
                events.extend(
                    [
                        ("pause", pause_pos, min(play["started_at"] + timedelta(minutes=6), complete_time)),
                        ("resume", resume_pos, min(play["started_at"] + timedelta(minutes=8), complete_time)),
                        ("complete", play["last_position_seconds"], complete_time),
                    ]
                )
            else:
                seek_pos = max(1, int(play["last_position_seconds"] * 0.6))
                end_time = play["ended_at"] or play["updated_at"]
                events.extend(
                    [
                        ("seek", seek_pos, min(play["started_at"] + timedelta(minutes=5), end_time)),
                        ("exit", play["last_position_seconds"], end_time),
                    ]
                )
            for index, (event_type, position_seconds, event_time) in enumerate(events, start=1):
                rows.append(
                    {
                        "play_session_id": play["id"],
                        "event_type": event_type,
                        "position_seconds": min(position_seconds, play["duration_seconds"]),
                        "playback_rate": self.random.choice(PLAYBACK_RATES),
                        "network_type": self.random.choice(NETWORK_TYPES),
                        "event_payload": json.dumps({"seq": index}, ensure_ascii=False),
                        "event_time": event_time,
                        "created_at": max(play["created_at"], event_time),
                    }
                )
        return self.insert_rows("session_video_play_event", rows)

    def generate_homework_submissions(self) -> int:
        rows: list[dict[str, Any]] = []
        teacher_map = self.fetch_session_teacher_map()
        homeworks = self.fetch_homeworks_with_context()
        fulfillments = self.fetch_effective_fulfillments_by_cohort()
        sequence = 1
        for homework in homeworks:
            for rel in fulfillments.get(homework["cohort_id"], []):
                created_at = max(homework["created_at"], rel["created_at"])
                teacher_id = teacher_map.get(homework["session_id"])
                can_submit = created_at <= homework["due_at"]
                submit_status = (
                    "submitted"
                    if can_submit and self.random.random() < 0.82
                    else "expired_unsubmitted"
                )
                correction_status = "pending"
                submitted_at = None
                corrected_at = None
                corrected_by = None
                total_score = None
                feedback_text = None
                if submit_status == "submitted":
                    submitted_at = self.random_datetime(created_at, homework["due_at"])
                    if self.random.random() < 0.7 and teacher_id is not None:
                        correction_status = "corrected"
                        corrected_by = teacher_id
                        corrected_at = self.cap_at_now(
                            submitted_at + timedelta(hours=self.random.randint(6, 72))
                        )
                        total_score = Decimal(str(self.random.randint(60, 100)))
                        feedback_text = "整体完成度不错，注意补充细节。"
                updated_at = max(
                    value
                    for value in (created_at, submitted_at, corrected_at)
                    if value is not None
                )
                rows.append(
                    {
                        "institution_id": homework["institution_id"],
                        "homework_id": homework["id"],
                        "user_id": rel["user_id"],
                        "student_id": rel["student_id"],
                        "session_id": homework["session_id"],
                        "submit_no": f"HWS{sequence:012d}",
                        "submit_status": submit_status,
                        "total_score": total_score,
                        "correction_status": correction_status,
                        "corrected_by": corrected_by,
                        "feedback_text": feedback_text,
                        "submitted_at": submitted_at,
                        "corrected_at": corrected_at,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }
                )
                sequence += 1
        return self.insert_rows("session_homework_submission", rows)

    def generate_exam_submissions(self) -> int:
        rows: list[dict[str, Any]] = []
        exams = self.fetch_exams_with_context()
        fulfillments = self.fetch_effective_fulfillments_by_cohort()
        sequence = 1
        for exam in exams:
            for rel in fulfillments.get(exam["cohort_id"], []):
                created_at = max(exam["created_at"], rel["created_at"])
                attempt_status = self.pick_exam_attempt_status()
                latest_start = exam["deadline_at"] - timedelta(minutes=exam["duration_minutes"])
                if created_at > latest_start:
                    attempt_status = "absent"
                start_at = None
                submit_at = None
                duration_seconds = None
                score_value = None
                if attempt_status in {"in_progress", "submitted", "timeout"}:
                    start_at = self.random_datetime(max(created_at, exam["window_start_at"]), latest_start)
                if attempt_status == "submitted":
                    if start_at is None:
                        raise ValueError("submitted exam attempt requires start_at")
                    duration_seconds = self.random.randint(
                        600, exam["duration_minutes"] * 60 - 60
                    )
                    submit_at = min(
                        exam["deadline_at"],
                        start_at + timedelta(seconds=duration_seconds),
                    )
                    score_value = Decimal(str(self.random.randint(55, int(exam["total_score"]))))
                elif attempt_status == "timeout":
                    if start_at is None:
                        raise ValueError("timeout exam attempt requires start_at")
                    duration_seconds = exam["duration_minutes"] * 60
                    submit_at = min(
                        exam["deadline_at"],
                        start_at + timedelta(seconds=duration_seconds),
                    )
                updated_at = max(
                    value
                    for value in (created_at, start_at, submit_at)
                    if value is not None
                )
                rows.append(
                    {
                        "institution_id": exam["institution_id"],
                        "exam_id": exam["id"],
                        "user_id": rel["user_id"],
                        "student_id": rel["student_id"],
                        "attempt_no": f"ATT{sequence:012d}",
                        "attempt_status": attempt_status,
                        "duration_seconds": duration_seconds,
                        "score_value": score_value,
                        "start_at": start_at,
                        "submit_at": submit_at,
                        "created_at": created_at,
                        "updated_at": updated_at,
                    }
                )
                sequence += 1
        return self.insert_rows("session_exam_submission", rows)

    def generate_discussion_topics(self) -> int:
        rows: list[dict[str, Any]] = []
        ratio = float(GENERATION_DEFAULTS["discussion_topic_ratio"])
        participants = self.fetch_discussion_participants_by_cohort()
        sequence = 1
        for cohort in self.fetch_cohorts_for_interaction():
            cohort_participants = participants.get(cohort["id"], [])
            if not cohort_participants:
                continue
            topic_count = max(1, int(len(cohort_participants) * ratio))
            for index in range(topic_count):
                creator = cohort_participants[index % len(cohort_participants)]
                created_at = self.random_datetime(
                    max(cohort["created_at"], creator["created_at"]),
                    self.now,
                )
                rows.append(
                    {
                        "institution_id": cohort["institution_id"],
                        "cohort_id": cohort["id"],
                        "creator_user_id": creator["user_id"],
                        "topic_title": TOPIC_TITLES[index % len(TOPIC_TITLES)],
                        "content_text": TOPIC_CONTENTS[index % len(TOPIC_CONTENTS)],
                        "is_pinned": 1 if index == 0 and self.random.random() < 0.25 else 0,
                        "is_closed": 0,
                        "view_count": 0,
                        "reply_count": 0,
                        "last_reply_at": None,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )
                sequence += 1
        return self.insert_rows("cohort_discussion_topic", rows)

    def generate_discussion_posts(self) -> int:
        rows: list[dict[str, Any]] = []
        topics = self.fetch_topics()
        participants = self.fetch_discussion_participants_by_cohort()
        for topic in topics:
            cohort_participants = participants.get(topic["cohort_id"], [])
            if not cohort_participants:
                continue
            direct_count = self.random.randint(1, min(4, len(cohort_participants)))
            direct_rows: list[dict[str, Any]] = []
            for index in range(direct_count):
                author = cohort_participants[(topic["id"] + index) % len(cohort_participants)]
                created_at = self.cap_at_now(topic["created_at"] + timedelta(hours=index + 1))
                direct_rows.append(
                    {
                        "institution_id": topic["institution_id"],
                        "topic_id": topic["id"],
                        "parent_post_id": None,
                        "author_user_id": author["user_id"],
                        "content_text": POST_CONTENTS[(topic["id"] + index) % len(POST_CONTENTS)],
                        "like_count": self.random.randint(0, 12),
                        "reply_count": 0,
                        "yn": 1,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )
            rows.extend(direct_rows)
        inserted = self.insert_rows("cohort_discussion_post", rows)

        direct_posts = db.fetch_all(
            """
            SELECT p.*, t.cohort_id
            FROM cohort_discussion_post AS p
            JOIN cohort_discussion_topic AS t ON t.id = p.topic_id
            WHERE p.parent_post_id IS NULL
            ORDER BY p.id
            """
        )
        child_rows: list[dict[str, Any]] = []
        participants = self.fetch_discussion_participants_by_cohort()
        for post in direct_posts:
            if self.random.random() > 0.55:
                continue
            cohort_participants = participants.get(post["cohort_id"], [])
            if not cohort_participants:
                continue
            author = cohort_participants[(post["id"] + 3) % len(cohort_participants)]
            created_at = self.cap_at_now(post["created_at"] + timedelta(hours=1))
            child_rows.append(
                {
                    "institution_id": post["institution_id"],
                    "topic_id": post["topic_id"],
                    "parent_post_id": post["id"],
                    "author_user_id": author["user_id"],
                    "content_text": POST_CONTENTS[(post["id"] + 1) % len(POST_CONTENTS)],
                    "like_count": self.random.randint(0, 6),
                    "reply_count": 0,
                    "yn": 1,
                    "created_at": created_at,
                    "updated_at": created_at,
                }
            )
        inserted += self.insert_rows("cohort_discussion_post", child_rows)
        return inserted

    def refresh_discussion_stats(self) -> None:
        db.execute(
            """
            UPDATE cohort_discussion_post AS post
            LEFT JOIN (
                SELECT
                    parent_post_id,
                    COUNT(*) AS reply_count
                FROM cohort_discussion_post
                WHERE parent_post_id IS NOT NULL
                  AND yn = 1
                GROUP BY parent_post_id
            ) AS child ON child.parent_post_id = post.id
            SET post.reply_count = COALESCE(child.reply_count, 0)
            """
        )
        db.execute(
            """
            UPDATE cohort_discussion_topic AS topic
            LEFT JOIN (
                SELECT
                    topic_id,
                    COUNT(*) AS reply_count,
                    MAX(created_at) AS last_reply_at
                FROM cohort_discussion_post
                WHERE parent_post_id IS NULL
                  AND yn = 1
                GROUP BY topic_id
            ) AS post_stats ON post_stats.topic_id = topic.id
            SET
                topic.reply_count = COALESCE(post_stats.reply_count, 0),
                topic.last_reply_at = post_stats.last_reply_at,
                topic.view_count = GREATEST(
                    topic.view_count,
                    COALESCE(post_stats.reply_count, 0) * 8 + 20
                ),
                topic.updated_at = GREATEST(
                    topic.created_at,
                    COALESCE(post_stats.last_reply_at, topic.created_at)
                )
            """
        )

    def generate_cohort_reviews(self) -> int:
        ratio = float(GENERATION_DEFAULTS["review_ratio"])
        rows: list[dict[str, Any]] = []
        sequence = 1
        for rel in self.fetch_reviewable_fulfillments():
            if self.random.random() > ratio:
                continue
            cohort_start_at = rel["cohort_start_at"]
            if isinstance(cohort_start_at, date) and not isinstance(cohort_start_at, datetime):
                cohort_start_at = datetime.combine(cohort_start_at, datetime.min.time())
            created_at = max(rel["created_at"], cohort_start_at)
            reviewed_at = self.random_datetime(created_at, self.now)
            tag_count = self.random.randint(1, 3)
            tags = self.random.sample(REVIEW_TAG_POOL, k=tag_count)
            rows.append(
                {
                    "institution_id": rel["institution_id"],
                    "cohort_id": rel["cohort_id"],
                    "user_id": rel["user_id"],
                    "student_id": rel["student_id"],
                    "review_no": f"REV{sequence:012d}",
                    "score_overall": self.random.randint(3, 5),
                    "score_teacher": self.random.randint(3, 5),
                    "score_content": self.random.randint(3, 5),
                    "score_service": self.random.randint(3, 5),
                    "review_tags": json.dumps(tags, ensure_ascii=False),
                    "review_content": "整体体验不错，课程内容和服务都比较满意。",
                    "anonymous_flag": 1 if self.random.random() < 0.35 else 0,
                    "yn": 1,
                    "reviewed_at": reviewed_at,
                    "created_at": created_at,
                    "updated_at": reviewed_at,
                }
            )
            sequence += 1
        return self.insert_rows("cohort_review", rows)

    def generate_service_tickets(self) -> int:
        ratio = float(GENERATION_DEFAULTS["service_ticket_ratio"])
        rows: list[dict[str, Any]] = []
        assignees = self.fetch_service_staff_by_institution()
        refunds_by_order_item = self.fetch_refunds_by_order_item()
        sequence = 1
        for item in self.fetch_service_ticket_candidates():
            if self.random.random() > ratio:
                continue
            refund = refunds_by_order_item.get(item["order_item_id"])
            ticket_type = "refund" if refund is not None and self.random.random() < 0.7 else self.random.choice(("after_sales", "complaint"))
            assignee_pool = assignees[item["institution_id"]]
            assignee = assignee_pool[sequence % len(assignee_pool)] if assignee_pool else None
            created_at = (
                max(item["created_at"], refund["created_at"])
                if refund is not None
                else item["created_at"]
            )
            status = self.random.choices(
                ("pending", "in_progress", "closed"),
                weights=(15, 35, 50),
                k=1,
            )[0]
            first_response_at = None
            closed_at = None
            if status in {"in_progress", "closed"}:
                first_response_at = self.cap_at_now(
                    created_at + timedelta(hours=self.random.randint(1, 24))
                )
            if status == "closed":
                if first_response_at is None:
                    raise ValueError("closed ticket requires first_response_at")
                closed_at = self.cap_at_now(
                    first_response_at + timedelta(hours=self.random.randint(2, 72))
                )
            updated_at = max(value for value in (created_at, first_response_at, closed_at) if value is not None)
            rows.append(
                {
                    "institution_id": item["institution_id"],
                    "ticket_no": f"TKT{sequence:012d}",
                    "user_id": item["user_id"],
                    "student_id": item["student_id"],
                    "order_item_id": item["order_item_id"],
                    "refund_request_id": refund["id"] if ticket_type == "refund" and refund is not None else None,
                    "ticket_type": ticket_type,
                    "ticket_source": "system_auto" if ticket_type == "refund" else self.random.choice(SERVICE_TICKET_SOURCES),
                    "priority_level": "high" if ticket_type == "complaint" else self.random.choice(PRIORITY_LEVELS),
                    "ticket_status": status,
                    "assignee_user_id": None if assignee is None else assignee["user_id"],
                    "title": f"{item['cohort_name']} {ticket_type}工单",
                    "ticket_content": "用户反馈课程服务相关问题，需要跟进处理。",
                    "yn": 1,
                    "first_response_at": first_response_at,
                    "closed_at": closed_at,
                    "created_at": created_at,
                    "updated_at": updated_at,
                }
            )
            sequence += 1
        return self.insert_rows("service_ticket", rows)

    def generate_service_ticket_follow_records(self) -> int:
        rows: list[dict[str, Any]] = []
        tickets = self.fetch_tickets()
        staff = self.fetch_service_staff_by_institution()
        for ticket in tickets:
            institution_staff = staff.get(ticket["institution_id"], [])
            if not institution_staff:
                continue
            follow_count = 1 if ticket["ticket_status"] == "pending" else self.random.randint(2, 4)
            for index in range(follow_count):
                follower = institution_staff[(ticket["id"] + index) % len(institution_staff)]
                created_at = self.cap_at_now(ticket["created_at"] + timedelta(hours=index + 1))
                followed_at = created_at
                if ticket["closed_at"] is not None and followed_at > ticket["closed_at"]:
                    followed_at = ticket["closed_at"]
                    created_at = followed_at
                follow_type = "refund_review" if ticket["ticket_type"] == "refund" and index == 0 else self.random.choice(FOLLOW_TYPES)
                if ticket["ticket_type"] != "refund" and follow_type == "refund_review":
                    follow_type = "status_update"
                follow_result = (
                    "resolved"
                    if ticket["ticket_status"] == "closed" and index == follow_count - 1
                    else self.random.choice(OPEN_FOLLOW_RESULTS)
                )
                rows.append(
                    {
                        "ticket_id": ticket["id"],
                        "follow_user_id": follower["user_id"],
                        "follow_type": follow_type,
                        "follow_channel": self.random.choice(FOLLOW_CHANNELS),
                        "follow_result": follow_result,
                        "follow_content": "已记录用户诉求并同步处理进展。",
                        "followed_at": followed_at,
                        "created_at": created_at,
                        "updated_at": created_at,
                    }
                )
        return self.insert_rows("service_ticket_follow_record", rows)

    def refresh_ticket_stats(self) -> None:
        db.execute(
            """
            UPDATE service_ticket AS ticket
            LEFT JOIN (
                SELECT
                    ticket_id,
                    MIN(followed_at) AS first_response_at,
                    MAX(followed_at) AS last_followed_at
                FROM service_ticket_follow_record
                GROUP BY ticket_id
            ) AS follow_stats ON follow_stats.ticket_id = ticket.id
            SET
                ticket.first_response_at = CASE
                    WHEN ticket.ticket_status = 'pending' THEN NULL
                    ELSE follow_stats.first_response_at
                END,
                ticket.closed_at = CASE
                    WHEN ticket.ticket_status = 'closed'
                    THEN GREATEST(
                        COALESCE(ticket.closed_at, ticket.created_at),
                        COALESCE(follow_stats.last_followed_at, ticket.created_at)
                    )
                    ELSE NULL
                END,
                ticket.updated_at = GREATEST(
                    ticket.created_at,
                    COALESCE(follow_stats.last_followed_at, ticket.created_at),
                    COALESCE(ticket.closed_at, ticket.created_at)
                )
            """
        )

    def generate_service_ticket_satisfaction_surveys(self) -> int:
        rows: list[dict[str, Any]] = []
        sequence = 1
        for ticket in self.fetch_closed_tickets():
            if self.random.random() > 0.65:
                continue
            created_at = ticket["closed_at"]
            surveyed_at = self.cap_at_now(
                created_at + timedelta(hours=self.random.randint(2, 72))
            )
            rows.append(
                {
                    "survey_no": f"SAT{sequence:012d}",
                    "user_id": ticket["user_id"],
                    "student_id": ticket["student_id"],
                    "ticket_id": ticket["id"],
                    "score_value": self.random.randint(3, 5),
                    "comment_text": "整体处理比较及时，沟通也比较顺畅。",
                    "yn": 1,
                    "surveyed_at": surveyed_at,
                    "created_at": created_at,
                    "updated_at": surveyed_at,
                }
            )
            sequence += 1
        return self.insert_rows("service_ticket_satisfaction_survey", rows)

    def pick_attendance_status(self) -> str:
        return self.random.choices(
            ATTENDANCE_STATUSES,
            weights=(72, 10, 8, 10),
            k=1,
        )[0]

    def pick_exam_attempt_status(self) -> str:
        return self.random.choices(
            ("submitted", "timeout", "absent"),
            weights=(78, 8, 14),
            k=1,
        )[0]

    def fetch_effective_fulfillments_by_cohort(self) -> dict[int, list[dict[str, Any]]]:
        rows = db.fetch_all(
            """
            SELECT *
            FROM student_cohort_rel
            WHERE enroll_status IN ('active', 'completed')
            ORDER BY cohort_id, id
            """
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["cohort_id"], []).append(row)
        return result

    def fetch_teachable_sessions(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                ss.*,
                c.cohort_id,
                cohort.institution_id
            FROM series_cohort_session AS ss
            JOIN series_cohort_course AS c ON c.id = ss.series_cohort_course_id
            JOIN series_cohort AS cohort ON cohort.id = c.cohort_id
            JOIN series AS s ON s.id = cohort.series_id
            WHERE s.delivery_mode IN ('online_live', 'offline_face_to_face')
              AND ss.created_at <= %s
              AND ss.teaching_date <= %s
            ORDER BY ss.id
            """,
            (self.now, self.today),
        )

    def fetch_videos_with_context(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                v.*,
                cohort.id AS cohort_id,
                cohort.institution_id
            FROM session_video AS v
            JOIN session_asset AS a ON a.id = v.asset_id
            JOIN series_cohort_session AS ss ON ss.id = a.session_id
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS cohort ON cohort.id = cc.cohort_id
            WHERE v.created_at <= %s
              AND ss.teaching_date <= %s
            ORDER BY v.id
            """,
            (self.now, self.today),
        )

    def fetch_video_play_with_duration(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                play.*,
                video.duration_seconds
            FROM session_video_play AS play
            JOIN session_video AS video ON video.id = play.video_id
            ORDER BY play.id
            """
        )

    def fetch_homeworks_with_context(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                hw.*,
                cohort.id AS cohort_id,
                cohort.institution_id
            FROM session_homework AS hw
            JOIN series_cohort_session AS ss ON ss.id = hw.session_id
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS cohort ON cohort.id = cc.cohort_id
            WHERE hw.created_at <= %s
              AND hw.due_at <= %s
            ORDER BY hw.id
            """,
            (self.now, self.now),
        )

    def fetch_exams_with_context(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                exam.*,
                cohort.id AS cohort_id,
                cohort.institution_id
            FROM session_exam AS exam
            JOIN series_cohort_session AS ss ON ss.id = exam.session_id
            JOIN series_cohort_course AS cc ON cc.id = ss.series_cohort_course_id
            JOIN series_cohort AS cohort ON cohort.id = cc.cohort_id
            WHERE exam.created_at <= %s
              AND exam.deadline_at <= %s
            ORDER BY exam.id
            """,
            (self.now, self.now),
        )

    def fetch_session_teacher_map(self) -> dict[int, int]:
        rows = db.fetch_all("SELECT session_id, teacher_id FROM session_teacher_rel")
        return {row["session_id"]: row["teacher_id"] for row in rows}

    def fetch_discussion_participants_by_cohort(self) -> dict[int, list[dict[str, Any]]]:
        student_rows = db.fetch_all(
            """
            SELECT
                rel.cohort_id,
                rel.user_id,
                rel.created_at
            FROM student_cohort_rel AS rel
            WHERE rel.enroll_status IN ('active', 'completed')
            ORDER BY rel.cohort_id, rel.id
            """
        )
        teacher_rows = db.fetch_all(
            """
            SELECT
                c.id AS cohort_id,
                staff.user_id,
                GREATEST(c.created_at, staff.created_at) AS created_at
            FROM series_cohort AS c
            JOIN staff_profile AS staff ON staff.institution_id = c.institution_id
            JOIN org_staff_role AS role ON role.id = staff.staff_role_id
            WHERE role.role_category IN ('teacher', 'academic')
            ORDER BY c.id, staff.id
            """
        )
        rows = student_rows + teacher_rows
        result: dict[int, list[dict[str, Any]]] = {}
        seen: set[tuple[int, int]] = set()
        for row in rows:
            key = (row["cohort_id"], row["user_id"])
            if key in seen:
                continue
            seen.add(key)
            result.setdefault(row["cohort_id"], []).append(row)
        return result

    def fetch_cohorts_for_interaction(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT *
            FROM series_cohort
            WHERE start_date <= %s
            ORDER BY id
            """,
            (self.today,),
        )

    def fetch_topics(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM cohort_discussion_topic ORDER BY id")

    def fetch_reviewable_fulfillments(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                rel.*,
                cohort.start_date AS cohort_start_at
            FROM student_cohort_rel AS rel
            JOIN series_cohort AS cohort ON cohort.id = rel.cohort_id
            WHERE rel.enroll_status IN ('active', 'completed')
              AND cohort.start_date <= %s
            ORDER BY rel.id
            """,
            (self.today,),
        )

    def fetch_service_ticket_candidates(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT
                item.id AS order_item_id,
                item.institution_id,
                item.user_id,
                item.student_id,
                item.item_name AS cohort_name,
                item.created_at
            FROM order_item AS item
            JOIN `order` AS o ON o.id = item.order_id
            WHERE o.order_status IN ('paid', 'completed', 'partial_refunded', 'refunded')
            ORDER BY item.id
            """
        )

    def fetch_refunds_by_order_item(self) -> dict[int, dict[str, Any]]:
        rows = db.fetch_all(
            """
            SELECT *
            FROM refund_request
            ORDER BY id
            """
        )
        result: dict[int, dict[str, Any]] = {}
        for row in rows:
            result.setdefault(row["order_item_id"], row)
        return result

    def fetch_service_staff_by_institution(self) -> dict[int, list[dict[str, Any]]]:
        rows = db.fetch_all(
            """
            SELECT staff.*
            FROM staff_profile AS staff
            JOIN org_staff_role AS role ON role.id = staff.staff_role_id
            WHERE role.role_category IN ('service', 'sales', 'management', 'academic')
            ORDER BY staff.institution_id, staff.id
            """
        )
        result: dict[int, list[dict[str, Any]]] = {}
        for row in rows:
            result.setdefault(row["institution_id"], []).append(row)
        return result

    def fetch_tickets(self) -> list[dict[str, Any]]:
        return db.fetch_all("SELECT * FROM service_ticket ORDER BY id")

    def fetch_closed_tickets(self) -> list[dict[str, Any]]:
        return db.fetch_all(
            """
            SELECT *
            FROM service_ticket
            WHERE ticket_status = 'closed'
            ORDER BY id
            """
        )
