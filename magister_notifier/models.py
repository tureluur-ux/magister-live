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


@dataclass
class NotificationRecord:
    id: str
    timestamp: str
    title: str
    message: str
    subject: str
    old_value: Optional[float] = None
    new_value: Optional[float] = None
