from datetime import datetime, timedelta
import requests
from uuid import uuid4

from .models import Grade, Homework, ScheduleItem


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

    @staticmethod
    def search_schools(query: str) -> list[str]:
        query = query.strip()
        if len(query) < 2:
            return []
        try:
            response = requests.get(
                "https://accounts.magister.net/challenges/tenant/search",
                params={"sessionId": "", "key": query},
                timeout=8,
            )
            response.raise_for_status()
            results = response.json()
            if not isinstance(results, list):
                return []
            names = [str(item.get("displayName", "")).strip() for item in results]
            return list(dict.fromkeys(name for name in names if name))[:12]
        except requests.RequestException:
            return []

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

    def fetch_schedule(self, days_ahead: int = 14) -> list[ScheduleItem]:
        if not self._session:
            raise RuntimeError("Niet ingelogd.")
        start = datetime.now().date()
        end = start + timedelta(days=days_ahead)
        lessons = self._session.get_schedule(
            _from=start.isoformat(),
            to=end.isoformat(),
            with_changes=True,
        ) or []
        items: list[ScheduleItem] = []
        for lesson in lessons:
            try:
                raw = lesson.json if hasattr(lesson, "json") else lesson
                subjects = lesson.get_subject_names() if hasattr(lesson, "get_subject_names") else None
                subject = (subjects or ["Overig"])[0]
                teachers = lesson.get_teacher_names() if hasattr(lesson, "get_teacher_names") else None
                teacher = ""
                if teachers:
                    teacher = str(teachers[0].get("Naam") or "")
                start_value = lesson.get_start_time() if hasattr(lesson, "get_start_time") else raw.get("Start")
                end_value = lesson.get_end_time() if hasattr(lesson, "get_end_time") else raw.get("Einde")
                date_value = str(start_value or "").split("T")[0].split(" ")[0]
                items.append(ScheduleItem(
                    id=str(lesson.get_id() if hasattr(lesson, "get_id") else raw.get("Id") or uuid4()),
                    date=date_value,
                    start=str(start_value or ""),
                    end=str(end_value or ""),
                    subject=str(subject),
                    description=str(lesson.get_description() if hasattr(lesson, "get_description") else raw.get("Omschrijving") or ""),
                    location=str(lesson.get_location() if hasattr(lesson, "get_location") else raw.get("Lokatie") or ""),
                    teacher=teacher,
                    cancelled=bool(lesson.is_cancelled()) if hasattr(lesson, "is_cancelled") else False,
                    has_homework=bool(raw.get("OpdrachtId")),
                ))
            except (AttributeError, KeyError, TypeError):
                continue
        return items

    def fetch_homework(self, days_ahead: int = 14) -> list[Homework]:
        homework: list[Homework] = []
        for lesson in self.fetch_schedule(days_ahead):
            if not lesson.has_homework:
                continue
            homework.append(Homework(
                id=lesson.id,
                subject=lesson.subject,
                description=lesson.description or "Huiswerk",
                start=lesson.start,
                end=lesson.end,
                location=lesson.location,
                cancelled=lesson.cancelled,
            ))
        return homework
