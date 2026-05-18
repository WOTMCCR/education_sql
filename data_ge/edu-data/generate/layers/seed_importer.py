"""Seed import helpers for Layer1."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ..config import SEEDS_DIR
from ..db import db
from ..insert_support import build_insert_sql, insert_dict_rows


class SeedImporter:
    """Imports CSV seeds and resolves business codes to primary keys."""

    def __init__(self, seeds_dir: Path | None = None) -> None:
        self.seeds_dir = seeds_dir or SEEDS_DIR

    def load_csv(self, relative_path: str) -> list[dict[str, Any]]:
        path = self.seeds_dir / relative_path
        if not path.exists():
            raise FileNotFoundError(f"missing seed file: {path}")

        rows: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            for row in reader:
                rows.append(
                    {
                        key: None if value in {"", "NULL"} else value
                        for key, value in row.items()
                    }
                )
        if not rows:
            raise ValueError(f"seed file is empty: {path}")
        return rows

    def insert_rows(self, table_name: str, rows: list[dict[str, Any]]) -> int:
        return insert_dict_rows(table_name, rows)

    def build_insert_sql(self, table_name: str, columns: list[str]) -> str:
        return build_insert_sql(table_name, columns)

    def fetch_id_map(self, table_name: str, code_column: str) -> dict[str, int]:
        rows = db.fetch_all(f"SELECT id, `{code_column}` AS code FROM `{table_name}`")
        return {str(row["code"]): int(row["id"]) for row in rows}

    def import_simple_table(self, table_name: str, relative_path: str) -> int:
        return self.insert_rows(table_name, self.load_csv(relative_path))

    def import_dim_course_category(self) -> int:
        source_rows = self.load_csv("1_foundation/dim_course_category.csv")
        count = 0
        code_to_id: dict[str, int] = {}

        for level in (1, 2, 3):
            rows: list[dict[str, Any]] = []
            for source in source_rows:
                if int(source["category_level"]) != level:
                    continue
                source = dict(source)
                parent_code = source.pop("parent_category_code")
                rows.append(
                    {
                        "parent_id": code_to_id.get(parent_code),
                        **source,
                    }
                )
            count += self.insert_rows("dim_course_category", rows)
            code_to_id.update(
                self.fetch_id_map("dim_course_category", "category_code")
            )
        return count

    def import_dim_grade(self) -> int:
        source_rows = self.load_csv("1_foundation/dim_grade.csv")
        count = 0
        code_to_id: dict[str, int] = {}

        for grade_type in ("stage", "grade"):
            rows: list[dict[str, Any]] = []
            for source in source_rows:
                if source["grade_type"] != grade_type:
                    continue
                source = dict(source)
                parent_code = source.pop("parent_grade_code")
                rows.append({"parent_id": code_to_id.get(parent_code), **source})
            count += self.insert_rows("dim_grade", rows)
            code_to_id.update(self.fetch_id_map("dim_grade", "grade_code"))
        return count

    def import_org_campus(self) -> int:
        institution_ids = self.fetch_id_map("org_institution", "institution_code")
        rows: list[dict[str, Any]] = []
        for source in self.load_csv("1_foundation/org_campus.csv"):
            source = dict(source)
            institution_code = source.pop("institution_code")
            rows.append(
                {
                    "institution_id": institution_ids[institution_code],
                    **source,
                }
            )
        return self.insert_rows("org_campus", rows)

    def import_org_department(self) -> int:
        institution_ids = self.fetch_id_map("org_institution", "institution_code")
        campuses = db.fetch_all(
            """
            SELECT
                c.id,
                c.campus_code,
                i.institution_code
            FROM org_campus AS c
            JOIN org_institution AS i ON i.id = c.institution_id
            """
        )
        campus_ids = {
            (row["institution_code"], row["campus_code"]): int(row["id"])
            for row in campuses
        }

        rows: list[dict[str, Any]] = []
        for source in self.load_csv("1_foundation/org_department.csv"):
            source = dict(source)
            institution_code = source.pop("institution_code")
            campus_code = source.pop("campus_code")
            rows.append(
                {
                    "institution_id": institution_ids[institution_code],
                    "campus_id": campus_ids[(institution_code, campus_code)],
                    "parent_id": None,
                    **source,
                }
            )
        return self.insert_rows("org_department", rows)

    def import_layer1_seeds(self) -> dict[str, int]:
        counts = {
            "dim_channel": self.import_simple_table(
                "dim_channel", "1_foundation/dim_channel.csv"
            ),
            "dim_course_category": self.import_dim_course_category(),
            "dim_question_type": self.import_simple_table(
                "dim_question_type", "1_foundation/dim_question_type.csv"
            ),
            "dim_learner_identity": self.import_simple_table(
                "dim_learner_identity",
                "1_foundation/dim_learner_identity.csv",
            ),
            "dim_grade": self.import_dim_grade(),
            "dim_education_level": self.import_simple_table(
                "dim_education_level",
                "1_foundation/dim_education_level.csv",
            ),
            "dim_learning_goal": self.import_simple_table(
                "dim_learning_goal", "1_foundation/dim_learning_goal.csv"
            ),
            "org_institution": self.import_simple_table(
                "org_institution", "1_foundation/org_institution.csv"
            ),
        }
        counts["org_campus"] = self.import_org_campus()
        counts["org_department"] = self.import_org_department()
        return counts
