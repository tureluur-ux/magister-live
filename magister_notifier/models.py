from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Grade:
    id: str
    subject: str
    value: float
    description: str = ""
    entered_at: str = ""
    weight: float = 1.0
    sufficient: bool = True


@dataclass
class Homework:
    id: str
    subject: str
    description: str
    start: str = ""
    end: str = ""
    location: str = ""
    cancelled: bool = False


@dataclass
class ScheduleItem:
    id: str
    date: str
    start: str
    end: str
    subject: str
    description: str = ""
    location: str = ""
    teacher: str = ""
    cancelled: bool = False
    has_homework: bool = False


def schedule_item_from_dict(data: dict) -> ScheduleItem:
    """Load current schedule data and migrate entries saved by older releases."""
    if "start" in data and "subject" in data:
        allowed = {
            "id", "date", "start", "end", "subject", "description",
            "location", "teacher", "cancelled", "has_homework",
        }
        values = {key: value for key, value in data.items() if key in allowed}
        return ScheduleItem(**values)

    start = str(data.get("Start") or "")
    subjects = data.get("Vakken") or []
    teachers = data.get("Docenten") or []
    subject = "Overig"
    if subjects and isinstance(subjects[0], dict):
        subject = str(subjects[0].get("Naam") or subjects[0].get("Omschrijving") or subject)
    teacher = ""
    if teachers and isinstance(teachers[0], dict):
        teacher = str(teachers[0].get("Naam") or "")
    return ScheduleItem(
        id=str(data.get("Id") or data.get("OpdrachtId") or f"legacy-{start}-{subject}"),
        date=start.split("T")[0].split(" ")[0],
        start=start,
        end=str(data.get("Einde") or ""),
        subject=subject,
        description=str(data.get("Omschrijving") or ""),
        location=str(data.get("Lokatie") or ""),
        teacher=teacher,
        cancelled=bool(data.get("cancelled", False)),
        has_homework=bool(data.get("OpdrachtId")),
    )


@dataclass
class NotificationRecord:
    id: str
    timestamp: str
    title: str
    message: str
    subject: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None
