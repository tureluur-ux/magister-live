from datetime import datetime, timedelta
from typing import Iterable

from .models import Grade, Homework


class MagisterClient:
    """Thin adapter around MagisterPy."""

    def __init__(self, school: str, username: str, password: str) -> None:
        self.school = school
        self.username = username
        self.password = password
        self._session = None

    def login(self) -> bool:
        try:
            from MagisterPy import MagisterSession
        except ImportError as exc:
            raise RuntimeError("MagisterPy is niet geïnstalleerd.") from exc

        self._session = MagisterSession(
            automatically_handle_errors=False,
            enable_automatic_relogin=True,
        )
        return bool(self._session.login(
            school_name=self.school,
            username=self.username,
            password=self.password,
        ))

    def fetch_grades(self, limit: int = 250) -> list[Grade]:
        if not self._session:
            raise RuntimeError("Niet ingelogd.")
        items = self._session.get_grades(top=limit) or []
        grades: list[Grade] = []
        for item in items:
            try:
                raw_value = item.get_value()
                value = float(str(raw_value).replace(",", "."))
            except (TypeError, ValueError):
                continue
            raw_id = item.get_id()
            grades.append(Grade(
                id=str(raw_id or f"{item.get_entered_time()}-{item.get_lesson_name()}"),
                subject=str(item.get_lesson_name() or item.get_lesson_code() or "Onbekend vak"),
                value=value,
                description=str(item.get("omschrijving") or ""),
                entered_at=str(item.get_entered_time() or ""),
                weight=float(item.get("weegfactor") or 1),
                sufficient=bool(item.get("isVoldoende", True)),
            ))
        return grades

    def fetch_schedule(self, days_ahead: int = 14) -> list[dict]:
        if not self._session:
            raise RuntimeError("Niet ingelogd.")
        start = datetime.now().date()
        end = start + timedelta(days=days_ahead)
        return self._session.get_schedule(
            _from=start.isoformat(),
            to=end.isoformat(),
            with_changes=True,
        ) or []

    def fetch_homework(self, days_ahead: int = 14) -> list[Homework]:
        homework: list[Homework] = []
        for lesson in self.fetch_schedule(days_ahead):
            try:
                assignment_id = lesson.get("OpdrachtId")
                if not assignment_id:
                    continue
                subjects = lesson.get_subject_names() or ["Onbekend vak"]
                homework.append(Homework(
                    id=str(assignment_id),
                    subject=subjects[0],
                    description=str(lesson.get_description() or "Huiswerk"),
                    start=str(lesson.get_start_time() or ""),
                    end=str(lesson.get_end_time() or ""),
                    location=str(lesson.get_location() or ""),
                    cancelled=lesson.is_cancelled(),
                ))
            except (AttributeError, KeyError, TypeError):
                continue
        return homework
