import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from tkinter import filedialog, messagebox

from .config import AppConfig
from .exporter import export_grades
from .magister_client import MagisterClient
from .models import Grade, Homework, NotificationRecord, ScheduleItem, schedule_item_from_dict
from .notifier import WindowsNotifier
from .startup import set_windows_startup
from .storage import JsonStore


class MagisterLiveApp(ctk.CTk):
    COLORS = {
        "background": "#0F1117",
        "sidebar": "#171A22",
        "card": "#1B1F29",
        "card_hover": "#222735",
        "border": "#2A3040",
        "text": "#F4F6FB",
        "muted": "#9DA6B8",
        "accent": "#4F86F7",
        "accent_hover": "#668FF7",
        "success": "#55C89A",
        "danger": "#FF7A7A",
    }

    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Magister Live")
        self.geometry("1280x820")
        self.minsize(1080, 700)
        self.configure(fg_color=self.COLORS["background"])

        self.store = JsonStore()
        self.config = AppConfig.load(self.store)
        self.notification_service = WindowsNotifier(self.config.sound)
        self.session: Optional[MagisterClient] = None
        self.sync_running = False
        self.week_offset = 0
        self.school_search_after = ""
        self.sync_status_labels: list[ctk.CTkLabel] = []

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.login_frame = self._build_login()
        self.app_frame = self._build_app()
        self.login_frame.pack(fill="both", expand=True)
        self.after(300_000, self._scheduled_sync)

    def _build_login(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color=self.COLORS["background"])
        self.login_card = ctk.CTkFrame(
            frame,
            width=470,
            fg_color=self.COLORS["card"],
            border_width=1,
            border_color=self.COLORS["border"],
            corner_radius=22,
        )
        self.login_card.place(relx=0.5, rely=0.5, anchor="center")
        self.login_step = 1
        self._show_login_step()
        return frame

    def _show_login_step(self) -> None:
        for widget in self.login_card.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.login_card,
            text="M",
            width=58,
            height=58,
            corner_radius=29,
            fg_color=self.COLORS["accent"],
            font=ctk.CTkFont(size=30, weight="bold"),
        ).pack(pady=(34, 12))
        ctk.CTkLabel(self.login_card, text="Magister Live", font=ctk.CTkFont(size=28, weight="bold")).pack()

        if self.login_step == 1:
            ctk.CTkLabel(self.login_card, text="Goedemorgen,", text_color="#A4C5FF", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(18, 4))
            ctk.CTkLabel(self.login_card, text="Voer je Magister-school-URL in", text_color=self.COLORS["muted"]).pack(pady=(0, 18))
            ctk.CTkLabel(self.login_card, text="School-URL", text_color=self.COLORS["muted"], anchor="w").pack(fill="x", padx=55)
            self.school_entry = ctk.CTkEntry(
                self.login_card,
                width=360,
                height=44,
                placeholder_text="bijv. schaersvoorde.magister.net",
            )
            self.school_entry.pack(pady=(6, 12))
            if self.config.school:
                self.school_entry.insert(0, self.config.school)
            self.school_entry.bind("<Return>", lambda event: self._continue_to_username())
            self.login_status = ctk.CTkLabel(self.login_card, text="", text_color=self.COLORS["danger"])
            self.login_status.pack()
            self.login_button = ctk.CTkButton(
                self.login_card, text="Doorgaan", height=46, fg_color=self.COLORS["accent"],
                hover_color=self.COLORS["accent_hover"], command=self._continue_to_username,
            )
            self.login_button.pack(pady=(14, 34), padx=55, fill="x")
        elif self.login_step == 2:
            ctk.CTkLabel(self.login_card, text="Vul je gebruikersnaam in", text_color=self.COLORS["text"], font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(18, 18))
            school_value = ctk.CTkFrame(self.login_card, fg_color="#243044", corner_radius=10)
            school_value.pack(fill="x", padx=55, pady=(0, 12))
            ctk.CTkLabel(school_value, text=f"  {getattr(self, 'selected_school', '')}", anchor="w").pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(school_value, text="Wijzig", text_color="#A4C5FF").pack(side="right", padx=12)
            self.username_entry = ctk.CTkEntry(self.login_card, width=360, height=44)
            self.username_entry.pack(pady=(6, 10))
            self.username_entry.insert(0, self.config.username)
            self.login_status = ctk.CTkLabel(self.login_card, text="", text_color=self.COLORS["danger"])
            self.login_status.pack()
            nav = ctk.CTkFrame(self.login_card, fg_color="transparent")
            nav.pack(fill="x", padx=55, pady=(14, 34))
            ctk.CTkButton(nav, text="Terug", width=100, fg_color="transparent", border_width=1, border_color=self.COLORS["border"], command=self._back_to_school).pack(side="left")
            self.login_button = ctk.CTkButton(nav, text="Doorgaan", width=240, fg_color=self.COLORS["accent"], command=self._continue_to_password)
            self.login_button.pack(side="right")
        else:
            ctk.CTkLabel(self.login_card, text="Wachtwoord invoeren", text_color=self.COLORS["text"], font=ctk.CTkFont(size=18, weight="bold")).pack(pady=(18, 18))
            account_value = ctk.CTkFrame(self.login_card, fg_color="#243044", corner_radius=10)
            account_value.pack(fill="x", padx=55, pady=(0, 12))
            ctk.CTkLabel(account_value, text=f"{getattr(self, 'selected_username', '')}", anchor="w").pack(side="left", fill="x", expand=True, padx=12, pady=10)
            ctk.CTkLabel(account_value, text="Wijzig", text_color="#A4C5FF").pack(side="right", padx=12)
            self.password_entry = ctk.CTkEntry(self.login_card, width=360, height=44, show="•")
            self.password_entry.pack(pady=(6, 10))
            self.login_status = ctk.CTkLabel(self.login_card, text="", text_color=self.COLORS["danger"])
            self.login_status.pack()
            nav = ctk.CTkFrame(self.login_card, fg_color="transparent")
            nav.pack(fill="x", padx=55, pady=(14, 34))
            ctk.CTkButton(nav, text="Terug", width=100, fg_color="transparent", border_width=1, border_color=self.COLORS["border"], command=self._back_to_username).pack(side="left")
            self.login_button = ctk.CTkButton(nav, text="Inloggen", width=240, fg_color=self.COLORS["accent"], command=self.login)
            self.login_button.pack(side="right")

    def _continue_to_username(self) -> None:
        if not self.school_entry.get().strip():
            self.login_status.configure(text="Kies eerst je school.")
            return
        self.selected_school = self.school_entry.get().strip()
        self.login_step = 2
        self._show_login_step()

    def _continue_to_password(self) -> None:
        if not self.username_entry.get().strip():
            self.login_status.configure(text="Vul je gebruikersnaam in.")
            return
        self.selected_username = self.username_entry.get().strip()
        self.login_step = 3
        self._show_login_step()

    def _back_to_school(self) -> None:
        school = getattr(self, "selected_school", "")
        self.login_step = 1
        self._show_login_step()
        self.school_entry.set(school)

    def _back_to_username(self) -> None:
        username = getattr(self, "selected_username", self.username_entry.get())
        self.login_step = 2
        self._show_login_step()
        self.username_entry.insert(0, username)

    def _login_enter(self) -> None:
        if self.login_step == 1:
            self._continue_to_username()
        elif self.login_step == 2:
            self._continue_to_password()
        else:
            self.login()

    def _schedule_school_search(self, event=None) -> None:
        if self.school_search_after:
            self.after_cancel(self.school_search_after)
        self.school_search_after = self.after(350, self._search_schools)

    def _search_schools(self) -> None:
        query = self.school_entry.get().strip()
        if len(query) < 2:
            return

        def run() -> None:
            schools = MagisterClient.search_schools(query)
            if schools:
                self.after(0, lambda: self._update_school_choices(schools))

        threading.Thread(target=run, daemon=True).start()

    def _update_school_choices(self, schools: list[str]) -> None:
        self.school_entry.configure(values=schools)

    def _school_selected(self, value: str) -> None:
        self.login_status.configure(text="")

    def _build_app(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color=self.COLORS["background"], corner_radius=0)
        sidebar = ctk.CTkFrame(frame, width=220, fg_color=self.COLORS["sidebar"], corner_radius=0)
        sidebar.pack(side="left", fill="y")
        ctk.CTkLabel(
            sidebar,
            text="Magister",
            font=ctk.CTkFont(size=23, weight="bold"),
        ).pack(padx=22, pady=(28, 30), anchor="w")

        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        for name in ("Home", "Rooster", "Cijfers", "Meldingen", "Instellingen"):
            button = ctk.CTkButton(
                sidebar,
                text=name,
                height=44,
                anchor="w",
                fg_color="transparent",
                hover_color=self.COLORS["card_hover"],
                text_color=self.COLORS["muted"],
                command=lambda n=name: self._show_page(n),
            )
            button.pack(fill="x", padx=12, pady=3)
            self.nav_buttons[name] = button

        self.page_host = ctk.CTkFrame(frame, fg_color=self.COLORS["background"])
        self.page_host.pack(side="left", fill="both", expand=True)
        self.pages = {
            "Home": self._build_home_page(),
            "Rooster": self._build_schedule_page(),
            "Cijfers": self._build_grades_page(),
            "Meldingen": self._build_notifications_page(),
            "Instellingen": self._build_settings_page(),
        }
        self.current_page = "Home"
        self._show_page("Home")
        return frame

    def _show_page(self, name: str) -> None:
        for page_name, page in self.pages.items():
            page.pack_forget()
        self.pages[name].pack(fill="both", expand=True)
        self.current_page = name
        for nav_name, button in self.nav_buttons.items():
            if nav_name == name:
                button.configure(fg_color=self.COLORS["accent"], text_color=self.COLORS["text"])
            else:
                button.configure(fg_color="transparent", text_color=self.COLORS["muted"])

    def _build_home_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_host, fg_color=self.COLORS["background"])
        header = self._page_header(page, "Vandaag", "Je Magister-overzicht")
        header.pack(fill="x", padx=24, pady=(20, 12))

        cards = ctk.CTkFrame(page, fg_color="transparent")
        cards.pack(fill="x", padx=24)
        self.next_lesson_card = self._metric_card(cards, "Volgende les", "Nog niet gesynchroniseerd")
        self.next_lesson_card.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.average_card = self._metric_card(cards, "Gemiddelde", "--")
        self.average_card.pack(side="left", fill="both", expand=True, padx=8)
        self.grade_card = self._metric_card(cards, "Laatste cijfer", "--")
        self.grade_card.pack(side="left", fill="both", expand=True, padx=(8, 0))

        content = ctk.CTkFrame(page, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=24, pady=16)
        left = ctk.CTkFrame(content, fg_color=self.COLORS["card"], corner_radius=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ctk.CTkLabel(left, text="Vandaag", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(16, 8))
        self.home_schedule_box = ctk.CTkTextbox(left, fg_color=self.COLORS["card"], border_width=0)
        self.home_schedule_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        right = ctk.CTkFrame(content, fg_color=self.COLORS["card"], corner_radius=14)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ctk.CTkLabel(right, text="Laatste meldingen", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(16, 8))
        self.home_notifications_box = ctk.CTkTextbox(right, fg_color=self.COLORS["card"], border_width=0)
        self.home_notifications_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        return page

    def _metric_card(self, parent, title: str, value: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, fg_color=self.COLORS["card"], corner_radius=14)
        ctk.CTkLabel(card, text=title, text_color=self.COLORS["muted"]).pack(anchor="w", padx=18, pady=(16, 4))
        value_label = ctk.CTkLabel(card, text=value, font=ctk.CTkFont(size=20, weight="bold"))
        value_label.pack(anchor="w", padx=18, pady=(0, 16))
        card.value_label = value_label
        return card

    def _page_header(self, parent, title: str, subtitle: str) -> ctk.CTkFrame:
        header = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(header, text=subtitle, text_color=self.COLORS["muted"]).pack(anchor="w", pady=(2, 0))
        status = ctk.CTkLabel(header, text="Nog niet gesynchroniseerd", text_color=self.COLORS["muted"])
        status.place(relx=1.0, rely=0.1, anchor="ne")
        self.sync_status_labels.append(status)
        ctk.CTkButton(
            header,
            text="Nu synchroniseren",
            width=155,
            height=38,
            fg_color=self.COLORS["accent"],
            command=self.manual_sync,
        ).place(relx=1.0, rely=0.75, anchor="ne")
        return header

    def _build_schedule_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_host, fg_color=self.COLORS["background"])
        header = ctk.CTkFrame(page, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 12))
        ctk.CTkLabel(header, text="Rooster", font=ctk.CTkFont(size=25, weight="bold")).pack(side="left")
        ctk.CTkButton(header, text="Vandaag", width=90, fg_color=self.COLORS["card_hover"], command=self._today_week).pack(side="right", padx=(8, 0))
        ctk.CTkButton(header, text="›", width=42, fg_color=self.COLORS["card_hover"], command=self._next_week).pack(side="right", padx=4)
        ctk.CTkButton(header, text="‹", width=42, fg_color=self.COLORS["card_hover"], command=self._previous_week).pack(side="right")
        self.week_label = ctk.CTkLabel(header, text="", text_color=self.COLORS["muted"])
        self.week_label.pack(side="right", padx=16)
        self.schedule_scroll = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self.schedule_scroll.pack(fill="both", expand=True, padx=24, pady=(4, 24))
        return page

    def _build_grades_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_host, fg_color=self.COLORS["background"])
        self._page_header(page, "Cijfers", "Laatste resultaten en ontwikkeling").pack(fill="x", padx=24, pady=(20, 12))
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="both", expand=True, padx=24, pady=(4, 16))
        left = ctk.CTkFrame(top, fg_color=self.COLORS["card"], corner_radius=14)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        ctk.CTkLabel(left, text="Laatste cijfers", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(16, 8))
        self.grades_box = ctk.CTkTextbox(left, fg_color=self.COLORS["card"], border_width=0)
        self.grades_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        right = ctk.CTkFrame(top, fg_color=self.COLORS["card"], corner_radius=14)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        ctk.CTkLabel(right, text="Gemiddelde per vak", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(16, 8))
        self.average_box = ctk.CTkTextbox(right, fg_color=self.COLORS["card"], border_width=0)
        self.average_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ctk.CTkButton(top, text="Exporteren naar Excel", command=self.export_excel).place(relx=1.0, rely=1.0, anchor="se")
        self.chart_frame = ctk.CTkFrame(page, fg_color=self.COLORS["card"], corner_radius=14)
        self.chart_frame.pack(fill="x", padx=24, pady=(0, 24), ipady=4)
        ctk.CTkLabel(self.chart_frame, text="Cijferontwikkeling", font=ctk.CTkFont(size=17, weight="bold")).pack(anchor="w", padx=18, pady=(12, 4))
        return page

    def _build_notifications_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_host, fg_color=self.COLORS["background"])
        self._page_header(page, "Meldingen", "Historie van ontvangen cijfermeldingen").pack(fill="x", padx=24, pady=(20, 12))
        card = ctk.CTkFrame(page, fg_color=self.COLORS["card"], corner_radius=14)
        card.pack(fill="both", expand=True, padx=24, pady=(4, 24))
        self.notifications_box = ctk.CTkTextbox(card, fg_color=self.COLORS["card"], border_width=0)
        self.notifications_box.pack(fill="both", expand=True, padx=12, pady=12)
        return page

    def _build_settings_page(self) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self.page_host, fg_color=self.COLORS["background"])
        ctk.CTkLabel(page, text="Instellingen", font=ctk.CTkFont(size=25, weight="bold")).pack(anchor="w", padx=24, pady=(20, 16))
        card = ctk.CTkFrame(page, fg_color=self.COLORS["card"], corner_radius=14)
        card.pack(anchor="nw", fill="x", padx=24)
        self.startup_switch = ctk.CTkSwitch(card, text="Starten met Windows")
        self.startup_switch.pack(anchor="w", padx=20, pady=(20, 12))
        self.sound_switch = ctk.CTkSwitch(card, text="Geluid bij nieuw cijfer")
        self.sound_switch.pack(anchor="w", padx=20, pady=12)
        if self.config.startup:
            self.startup_switch.select()
        if self.config.sound:
            self.sound_switch.select()
        ctk.CTkButton(card, text="Voorkeuren opslaan", fg_color=self.COLORS["accent"], command=self.save_settings).pack(anchor="w", padx=20, pady=(12, 20))
        return page

    def _previous_week(self) -> None:
        self.week_offset -= 1
        self._refresh_schedule_cache()

    def _next_week(self) -> None:
        self.week_offset += 1
        self._refresh_schedule_cache()

    def _today_week(self) -> None:
        self.week_offset = 0
        self._refresh_schedule_cache()

    def login(self) -> None:
        school = getattr(self, "selected_school", "").strip()
        if not school:
            self.login_status.configure(text="Voer eerst een Magister-school-URL in.")
            return
        username = getattr(self, "selected_username", "").strip()
        password_entry = getattr(self, "password_entry", None)
        password = password_entry.get() if password_entry else ""
        if not username or not password:
            self.login_status.configure(text="Vul je gebruikersnaam en wachtwoord in.")
            return
        self.login_status.configure(text="Veilig aanmelden bij Magister...")
        self.login_button.configure(state="disabled")

        def run() -> None:
            try:
                host, tenant = MagisterClient.normalize_school(school)
                client = MagisterClient(tenant, username, password)
                if not client.login():
                    raise RuntimeError("Inloggen mislukt. Controleer de school, gebruikersnaam en wachtwoord.")
                self.session = client
                self.config.school = host
                self.config.username = username
                self.config.save(self.store)
                self.after(0, self._show_app)
            except Exception as exc:
                self.after(0, lambda error=str(exc): self._login_failed(error))

        threading.Thread(target=run, daemon=True).start()

    def _login_failed(self, message: str) -> None:
        self.login_status.configure(text=message)
        self.login_button.configure(state="normal")

    def _show_app(self) -> None:
        self.login_frame.pack_forget()
        self.app_frame.pack(fill="both", expand=True)
        cached_grades = [Grade(**item) for item in self.store.get("grades", [])]
        cached_schedule = [
            schedule_item_from_dict(item)
            for item in self.store.get("schedule", [])
            if isinstance(item, dict)
        ]
        cached_notifications = self.store.get("notifications", [])
        self._refresh_all(cached_grades, cached_schedule, cached_notifications)
        self.manual_sync()

    def manual_sync(self) -> None:
        if not self.session or self.sync_running:
            return
        self.sync_running = True
        for label in self.sync_status_labels:
            if label.winfo_exists():
                label.configure(text="Synchroniseren...", text_color=self.COLORS["muted"])

        def run() -> None:
            try:
                grades = self.session.fetch_grades()
                schedule = self.session.fetch_schedule()
                homework = [
                    Homework(
                        id=item.id,
                        subject=item.subject,
                        description=item.description or "Huiswerk",
                        start=item.start,
                        end=item.end,
                        location=item.location,
                        cancelled=item.cancelled,
                    )
                    for item in schedule
                    if item.has_homework
                ]
                self._process_results(grades, homework, schedule)
            except Exception as exc:
                self.after(0, lambda error=str(exc): self._sync_failed(error))
            finally:
                self.sync_running = False

        threading.Thread(target=run, daemon=True).start()

    def _scheduled_sync(self) -> None:
        self.manual_sync()
        self.after(300_000, self._scheduled_sync)

    def _sync_failed(self, message: str) -> None:
        for label in self.sync_status_labels:
            if label.winfo_exists():
                label.configure(text=f"Sync mislukt: {message}", text_color=self.COLORS["danger"])

    def _process_results(self, grades: list[Grade], homework: list[Homework], schedule: list[ScheduleItem]) -> None:
        old_items = self.store.get("grades", [])
        old_grades = {item["id"]: item for item in old_items}
        records = self.store.get("notifications", [])
        new_records: list[dict] = []

        if old_grades:
            for grade in grades:
                old = old_grades.get(grade.id)
                if old is None:
                    title = "Nieuw cijfer"
                    message = f"Nieuw cijfer ontvangen! {grade.subject}: {grade.value:.1f}".replace(".", ",")
                    old_value = None
                else:
                    old_value = float(old.get("value", grade.value))
                    if old_value == grade.value:
                        continue
                    title = "Cijfer aangepast"
                    message = (
                        f"Cijfer aangepast! {grade.subject}: "
                        f"{old_value:.1f} -> {grade.value:.1f}"
                    ).replace(".", ",")
                record = NotificationRecord(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now().isoformat(timespec="seconds"),
                    title=title,
                    message=message,
                    subject=grade.subject,
                    old_value=old_value,
                    new_value=grade.value,
                )
                new_records.append(record.__dict__)
                self.notification_service.show(title, message)

        records = new_records + records
        self.store.set("grades", [grade.__dict__ for grade in grades])
        self.store.set("homework", [item.__dict__ for item in homework])
        self.store.set("schedule", [item.__dict__ for item in schedule])
        self.store.set("notifications", records[:200])
        self.after(0, lambda: self._refresh_all(grades, schedule, records))

    def _refresh_all(self, grades: list[Grade], schedule: list[ScheduleItem], records: list[dict]) -> None:
        now = datetime.now()
        for label in self.sync_status_labels:
            if label.winfo_exists():
                label.configure(
                    text=f"Laatst gesynchroniseerd {now.strftime('%H:%M:%S')}",
                    text_color=self.COLORS["muted"],
                )
        self._refresh_grades(grades)
        self._refresh_schedule(schedule)
        self._refresh_notifications(records)
        self._refresh_home(grades, schedule, records)
        self._draw_chart(grades)

    def _refresh_grades(self, grades: list[Grade]) -> None:
        self.grades_box.configure(state="normal")
        self.grades_box.delete("1.0", "end")
        for grade in sorted(grades, key=lambda item: item.entered_at, reverse=True)[:50]:
            self.grades_box.insert("end", f"{grade.subject:<20}  {grade.value:.1f}\n".replace(".", ","))
        self.grades_box.configure(state="disabled")

        averages: dict[str, list[float]] = {}
        for grade in grades:
            averages.setdefault(grade.subject, []).append(grade.value)
        self.average_box.configure(state="normal")
        self.average_box.delete("1.0", "end")
        for subject, values in sorted(averages.items()):
            average = sum(values) / len(values)
            self.average_box.insert("end", f"{subject:<20}  {average:.1f}\n".replace(".", ","))
        self.average_box.configure(state="disabled")
        if grades:
            all_values = [grade.value for grade in grades]
            self.average_card.value_label.configure(text=f"{sum(all_values) / len(all_values):.1f}".replace(".", ","))
            latest = sorted(grades, key=lambda item: item.entered_at, reverse=True)[0]
            self.grade_card.value_label.configure(text=f"{latest.subject}  {latest.value:.1f}".replace(".", ","))

    def _refresh_schedule_cache(self) -> None:
        schedule = [
            schedule_item_from_dict(item)
            for item in self.store.get("schedule", [])
            if isinstance(item, dict)
        ]
        self._refresh_schedule(schedule)

    def _week_dates(self) -> list[datetime]:
        today = datetime.now().date()
        monday = today - timedelta(days=today.weekday()) + timedelta(weeks=self.week_offset)
        return [datetime.combine(monday + timedelta(days=index), datetime.min.time()) for index in range(7)]

    def _refresh_schedule(self, schedule: list[ScheduleItem]) -> None:
        week_dates = self._week_dates()
        first = week_dates[0].date()
        last = week_dates[-1].date()
        self.week_label.configure(text=f"{first.strftime('%d %b')} – {last.strftime('%d %b %Y')}")

        for widget in self.schedule_scroll.winfo_children():
            widget.destroy()

        if not schedule:
            ctk.CTkLabel(
                self.schedule_scroll,
                text="Synchroniseer om je rooster te tonen.",
                text_color=self.COLORS["muted"],
            ).pack(pady=40)
            return

        for day in week_dates:
            day_items = sorted(
                [item for item in schedule if item.date.startswith(day.strftime("%Y-%m-%d"))],
                key=lambda item: item.start,
            )
            day_frame = ctk.CTkFrame(
                self.schedule_scroll,
                fg_color=self.COLORS["card"],
                corner_radius=14,
            )
            day_frame.pack(fill="x", pady=5)
            title = day.strftime("%A %d %b")
            ctk.CTkLabel(day_frame, text=title, width=150, font=ctk.CTkFont(size=14, weight="bold")).pack(side="left", padx=16, pady=16)

            if not day_items:
                ctk.CTkLabel(day_frame, text="Geen lessen", text_color=self.COLORS["muted"]).pack(side="left", pady=16)
                continue
            for item in day_items:
                card = ctk.CTkFrame(day_frame, fg_color=self.COLORS["card_hover"], corner_radius=10)
                card.pack(side="left", fill="x", expand=True, padx=5, pady=10)
                time_text = f"{item.start[11:16]} – {item.end[11:16]}".strip()
                ctk.CTkLabel(card, text=time_text, text_color=self.COLORS["accent"], font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", padx=12, pady=(8, 2))
                ctk.CTkLabel(card, text=item.subject, font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=12)
                details = item.location or item.description or ""
                if item.has_homework:
                    details = f"{details}  •  Huiswerk" if details else "Huiswerk"
                ctk.CTkLabel(card, text=details, text_color=self.COLORS["muted"]).pack(anchor="w", padx=12, pady=(2, 8))
                if item.cancelled:
                    card.configure(fg_color="#42202A")
                    ctk.CTkLabel(card, text="Geannuleerd", text_color=self.COLORS["danger"]).pack(anchor="w", padx=12, pady=(0, 8))

    def _refresh_home(self, grades: list[Grade], schedule: list[ScheduleItem], records: list[dict]) -> None:
        today = datetime.now().strftime("%Y-%m-%d")
        today_items = sorted(
            [item for item in schedule if item.date.startswith(today)],
            key=lambda item: item.start,
        )
        now_time = datetime.now().strftime("%H:%M")
        upcoming = next((item for item in today_items if item.start[11:16] >= now_time and not item.cancelled), None)
        if upcoming:
            self.next_lesson_card.value_label.configure(
                text=f"{upcoming.start[11:16]}  {upcoming.subject}"
            )
        elif today_items:
            self.next_lesson_card.value_label.configure(text="Geen volgende les")
        else:
            self.next_lesson_card.value_label.configure(text="Geen lessen")

        self.home_schedule_box.configure(state="normal")
        self.home_schedule_box.delete("1.0", "end")
        if today_items:
            for item in today_items:
                status = "  •  Geannuleerd" if item.cancelled else ""
                if item.has_homework:
                    status += "  •  Huiswerk"
                self.home_schedule_box.insert(
                    "end",
                    f"{item.start[11:16]} – {item.end[11:16]}  {item.subject}\n"
                    f"{item.location or item.description or ' '}{status}\n\n",
                )
        else:
            self.home_schedule_box.insert("end", "Geen lessen gepland vandaag.")
        self.home_schedule_box.configure(state="disabled")

        self.home_notifications_box.configure(state="normal")
        self.home_notifications_box.delete("1.0", "end")
        for record in records[:12]:
            stamp = str(record.get("timestamp", ""))[11:16]
            self.home_notifications_box.insert("end", f"{stamp}  {record.get('message', '')}\n\n")
        if not records:
            self.home_notifications_box.insert("end", "Nog geen nieuwe meldingen.")
        self.home_notifications_box.configure(state="disabled")

    def _refresh_notifications(self, records: list[dict]) -> None:
        self.notifications_box.configure(state="normal")
        self.notifications_box.delete("1.0", "end")
        for record in records:
            stamp = str(record.get("timestamp", "")).replace("T", " ")[0:16]
            self.notifications_box.insert("end", f"{stamp}\n{record.get('message', '')}\n\n")
        if not records:
            self.notifications_box.insert("end", "Er zijn nog geen cijfermeldingen ontvangen.")
        self.notifications_box.configure(state="disabled")

    def _draw_chart(self, grades: list[Grade]) -> None:
        if hasattr(self, "_chart_canvas"):
            self._chart_canvas.get_tk_widget().destroy()
        figure = Figure(figsize=(9.2, 2.2), facecolor=self.COLORS["card"])
        axis = figure.add_subplot(111)
        axis.set_facecolor(self.COLORS["card"])
        axis.tick_params(colors=self.COLORS["muted"])
        axis.spines["bottom"].set_color(self.COLORS["border"])
        axis.spines["left"].set_color(self.COLORS["border"])
        for subject in sorted({grade.subject for grade in grades})[:8]:
            points = sorted(
                (grade.entered_at, grade.value)
                for grade in grades
                if grade.subject == subject
            )
            if points:
                axis.plot(
                    range(len(points)),
                    [point[1] for point in points],
                    marker="o",
                    label=subject,
                )
        if axis.lines:
            axis.legend(facecolor=self.COLORS["card"], labelcolor="white", fontsize=8)
        axis.grid(True, alpha=0.12)
        self._chart_canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
        self._chart_canvas.draw()
        self._chart_canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=(4, 12))

    def save_settings(self) -> None:
        self.config.startup = bool(self.startup_switch.get())
        self.config.sound = bool(self.sound_switch.get())
        self.config.save(self.store)
        self.notification_service.set_sound(self.config.sound)
        try:
            set_windows_startup(self.config.startup)
            messagebox.showinfo("Instellingen", "Instellingen opgeslagen.")
        except Exception as exc:
            messagebox.showerror("Instellingen", f"Kan opstartinstelling niet wijzigen:\n{exc}")

    def export_excel(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Cijfers exporteren",
            defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
        )
        if not path:
            return
        grades = [Grade(**item) for item in self.store.get("grades", [])]
        try:
            export_grades(grades, Path(path))
            messagebox.showinfo("Exporteren", "Cijfers succesvol geëxporteerd.")
        except Exception as exc:
            messagebox.showerror("Exporteren", f"Export mislukt:\n{exc}")
