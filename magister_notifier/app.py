import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from .config import AppConfig
from .exporter import export_grades
from .magister_client import MagisterClient
from .models import Grade, Homework, NotificationRecord
from .notifications import NotificationService
from .startup import set_windows_startup
from .storage import JsonStore


class MagisterNotifierApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Magister Notifier")
        self.geometry("1180x760")
        self.minsize(980, 650)

        self.store = JsonStore()
        self.config = AppConfig.load(self.store)
        self.notification_service = NotificationService(self.config.sound)
        self.session: Optional[MagisterClient] = None
        self.sync_thread: Optional[threading.Thread] = None
        self.sync_running = False

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True)
        self.login_frame = self._build_login()
        self.dashboard_frame = self._build_dashboard()
        self.login_frame.pack(fill="both", expand=True)

        self.after(300_000, self._scheduled_sync)

    def _build_login(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="#151922")
        card = ctk.CTkFrame(frame, width=430, corner_radius=18)
        card.place(relx=0.5, rely=0.5, anchor="center")
        ctk.CTkLabel(card, text="Magister Notifier", font=ctk.CTkFont(size=28, weight="bold")).pack(pady=(32, 8))
        ctk.CTkLabel(card, text="Log in op je Magister-account", text_color="#AAB2C0").pack(pady=(0, 24))
        self.school_entry = ctk.CTkEntry(card, width=330, placeholder_text="Schoolnaam")
        self.school_entry.pack(pady=8)
        self.username_entry = ctk.CTkEntry(card, width=330, placeholder_text="Gebruikersnaam")
        self.username_entry.pack(pady=8)
        self.password_entry = ctk.CTkEntry(card, width=330, placeholder_text="Wachtwoord", show="•")
        self.password_entry.pack(pady=8)
        self.school_entry.insert(0, self.config.school)
        self.username_entry.insert(0, self.config.username)
        self.login_status = ctk.CTkLabel(card, text="", text_color="#FF8A8A")
        self.login_status.pack(pady=(8, 0))
        ctk.CTkButton(card, text="Inloggen", height=42, command=self.login).pack(pady=(16, 32), padx=50, fill="x")
        return frame

    def _build_dashboard(self) -> ctk.CTkFrame:
        frame = ctk.CTkFrame(self.container, fg_color="#10131A")

        sidebar = ctk.CTkFrame(frame, width=210, fg_color="#171B24", corner_radius=0)
        sidebar.pack(side="left", fill="y")
        ctk.CTkLabel(sidebar, text="Magister\nNotifier", font=ctk.CTkFont(size=22, weight="bold"), justify="left").pack(pady=28, padx=20, anchor="w")
        ctk.CTkButton(sidebar, text="Dashboard", fg_color="#2A62A5", hover_color="#3476C5", command=lambda: self.tabview.set("Dashboard")).pack(padx=16, pady=(10, 6), fill="x")
        ctk.CTkButton(sidebar, text="Instellingen", fg_color="transparent", hover_color="#252B38", command=lambda: self.tabview.set("Instellingen")).pack(padx=16, pady=6, fill="x")
        ctk.CTkButton(sidebar, text="Rooster / huiswerk", fg_color="transparent", hover_color="#252B38", command=lambda: self.tabview.set("Rooster")).pack(padx=16, pady=6, fill="x")

        main = ctk.CTkFrame(frame, fg_color="#10131A")
        main.pack(side="left", fill="both", expand=True)
        top = ctk.CTkFrame(main, fg_color="#171B24", height=72)
        top.pack(fill="x", padx=20, pady=(16, 8))
        ctk.CTkLabel(top, text="Overzicht", font=ctk.CTkFont(size=20, weight="bold")).pack(side="left", padx=18, pady=16)
        self.sync_status = ctk.CTkLabel(top, text="Nog niet gesynchroniseerd", text_color="#AAB2C0")
        self.sync_status.pack(side="left", padx=10)
        ctk.CTkButton(top, text="Synchroniseren", command=self.manual_sync).pack(side="right", padx=18, pady=14)

        self.tabview = ctk.CTkTabview(main)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=8)
        self.tabview.add("Dashboard")
        self.tabview.add("Rooster")
        self.tabview.add("Instellingen")
        self._build_dashboard_tab()
        self._build_schedule_tab()
        self._build_settings_tab()
        return frame

    def _build_dashboard_tab(self) -> None:
        tab = self.tabview.tab("Dashboard")
        columns = ctk.CTkFrame(tab, fg_color="transparent")
        columns.pack(fill="both", expand=True)

        left = ctk.CTkFrame(columns)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8), pady=8)
        ctk.CTkLabel(left, text="Laatste cijfers", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.grades_box = ctk.CTkTextbox(left, height=270)
        self.grades_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        right = ctk.CTkFrame(columns)
        right.pack(side="right", fill="both", expand=True, padx=(8, 0), pady=8)
        ctk.CTkLabel(right, text="Gemiddelde per vak", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.average_box = ctk.CTkTextbox(right, height=270)
        self.average_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        bottom = ctk.CTkFrame(tab)
        bottom.pack(fill="both", expand=True, pady=(0, 8))
        ctk.CTkLabel(bottom, text="Laatste meldingen", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(12, 6))
        self.notifications_box = ctk.CTkTextbox(bottom, height=150)
        self.notifications_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        ctk.CTkButton(bottom, text="Cijfers exporteren naar Excel", command=self.export_excel).pack(anchor="e", padx=12, pady=(0, 12))

    def _build_schedule_tab(self) -> None:
        tab = self.tabview.tab("Rooster")
        paned = ctk.CTkFrame(tab)
        paned.pack(fill="both", expand=True)
        ctk.CTkLabel(paned, text="Rooster en huiswerk", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=12)
        self.schedule_box = ctk.CTkTextbox(paned)
        self.schedule_box.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.chart_frame = ctk.CTkFrame(tab)
        self.chart_frame.pack(fill="both", expand=True)
        ctk.CTkLabel(self.chart_frame, text="Cijferontwikkeling", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=12)

    def _build_settings_tab(self) -> None:
        tab = self.tabview.tab("Instellingen")
        card = ctk.CTkFrame(tab)
        card.pack(anchor="nw", fill="x", padx=20, pady=20)
        ctk.CTkLabel(card, text="Voorkeuren", font=ctk.CTkFont(size=18, weight="bold")).pack(anchor="w", padx=20, pady=(20, 12))
        self.startup_switch = ctk.CTkSwitch(card, text="Starten met Windows")
        self.startup_switch.pack(anchor="w", padx=20, pady=10)
        self.sound_switch = ctk.CTkSwitch(card, text="Geluid bij een nieuw cijfer")
        self.sound_switch.pack(anchor="w", padx=20, pady=10)
        if self.config.startup:
            self.startup_switch.select()
        if self.config.sound:
            self.sound_switch.select()
        ctk.CTkButton(card, text="Voorkeuren opslaan", command=self.save_settings).pack(anchor="w", padx=20, pady=(16, 20))

    def login(self) -> None:
        school = self.school_entry.get().strip()
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        if not school or not username or not password:
            self.login_status.configure(text="Vul alle velden in.")
            return
        self.login_status.configure(text="Inloggen...")
        self.update()

        def run() -> None:
            try:
                client = MagisterClient(school, username, password)
                if not client.login():
                    raise RuntimeError("Inloggen is mislukt. Controleer de gegevens.")
                self.session = client
                self.config.school = school
                self.config.username = username
                self.config.save(self.store)
                self.after(0, self._show_dashboard)
            except Exception as exc:
                self.after(0, lambda: self.login_status.configure(text=str(exc)))

        threading.Thread(target=run, daemon=True).start()

    def _show_dashboard(self) -> None:
        self.login_frame.pack_forget()
        self.dashboard_frame.pack(fill="both", expand=True)
        cached_grades = [Grade(**item) for item in self.store.get("grades", [])]
        cached_homework = [Homework(**item) for item in self.store.get("homework", [])]
        self._refresh_ui(
            cached_grades,
            cached_homework,
            self.store.get("notifications", []),
        )
        self.manual_sync()

    def manual_sync(self) -> None:
        if not self.session or self.sync_running:
            return
        self.sync_running = True
        self.sync_status.configure(text="Synchroniseren...")

        def run() -> None:
            try:
                grades = self.session.fetch_grades()
                homework = self.session.fetch_homework()
                schedule = self.session.fetch_schedule()
                self._process_results(grades, homework, schedule)
            except Exception as exc:
                self.after(0, lambda: self.sync_status.configure(text=f"Sync mislukt: {exc}"))
            finally:
                self.sync_running = False

        threading.Thread(target=run, daemon=True).start()

    def _scheduled_sync(self) -> None:
        self.manual_sync()
        self.after(300_000, self._scheduled_sync)

    def _process_results(self, grades: list[Grade], homework: list[Homework], schedule: list) -> None:
        old_grades = {
            item["id"]: item
            for item in self.store.get("grades", [])
        }
        records: list[NotificationRecord] = self._notification_records()
        new_notifications: list[NotificationRecord] = []

        for grade in grades:
            if grade.id not in old_grades:
                record = NotificationRecord(
                    id=str(uuid.uuid4()),
                    timestamp=datetime.now().isoformat(timespec="seconds"),
                    title="Nieuw cijfer",
                    message=f"Nieuw cijfer ontvangen! {grade.subject}: {grade.value:.1f}".replace(".", ","),
                    subject=grade.subject,
                    new_value=grade.value,
                )
                new_notifications.append(record)
            else:
                old_value = float(old_grades[grade.id].get("value", 0))
                if old_value != grade.value:
                    record = NotificationRecord(
                        id=str(uuid.uuid4()),
                        timestamp=datetime.now().isoformat(timespec="seconds"),
                        title="Cijfer aangepast",
                        message=(
                            f"Cijfer aangepast! {grade.subject}: "
                            f"{old_value:.1f} -> {grade.value:.1f}"
                        ).replace(".", ","),
                        subject=grade.subject,
                        old_value=old_value,
                        new_value=grade.value,
                    )
                    new_notifications.append(record)

        for record in new_notifications:
            records.insert(0, record.__dict__)
            self.notification_service.show(record.title, record.message)

        self.store.set("grades", [grade.__dict__ for grade in grades])
        self.store.set("homework", [item.__dict__ for item in homework])
        self.store.set("schedule", [item.json for item in schedule if hasattr(item, "json")])
        self.store.set("notifications", records[:200])
        self.after(0, lambda: self._refresh_ui(grades, homework, records))

    def _notification_records(self) -> list[dict]:
        value = self.store.get("notifications", [])
        return value if isinstance(value, list) else []

    def _refresh_ui(self, grades: list[Grade], homework: list[Homework], records: list[dict]) -> None:
        self.sync_status.configure(text=f"Laatst gesynchroniseerd {datetime.now().strftime('%H:%M:%S')}")
        self.grades_box.configure(state="normal")
        self.grades_box.delete("1.0", "end")
        for grade in sorted(grades, key=lambda item: item.entered_at, reverse=True)[:40]:
            self.grades_box.insert("end", f"{grade.subject:<18}  {grade.value:.1f}\n".replace(".", ","))
        self.grades_box.configure(state="disabled")

        averages: dict[str, list[float]] = {}
        for grade in grades:
            averages.setdefault(grade.subject, []).append(grade.value)
        self.average_box.configure(state="normal")
        self.average_box.delete("1.0", "end")
        for subject, values in sorted(averages.items()):
            self.average_box.insert("end", f"{subject:<18}  {sum(values) / len(values):.1f}\n".replace(".", ","))
        self.average_box.configure(state="disabled")

        self.notifications_box.configure(state="normal")
        self.notifications_box.delete("1.0", "end")
        for record in records[:30]:
            stamp = str(record.get("timestamp", ""))[11:16]
            self.notifications_box.insert("end", f"{stamp}  {record.get('message', '')}\n")
        self.notifications_box.configure(state="disabled")

        self.schedule_box.configure(state="normal")
        self.schedule_box.delete("1.0", "end")
        if homework:
            for item in homework:
                status = " [geannuleerd]" if item.cancelled else ""
                self.schedule_box.insert("end", f"{item.start[:16]}  {item.subject}: {item.description}{status}\n")
        else:
            self.schedule_box.insert("end", "Geen opdrachten gevonden in het rooster.")
        self.schedule_box.configure(state="disabled")
        self._draw_chart(grades)

    def _draw_chart(self, grades: list[Grade]) -> None:
        if hasattr(self, "_chart_canvas"):
            self._chart_canvas.get_tk_widget().destroy()
        figure = Figure(figsize=(8, 2.8), facecolor="#1A1D24")
        axis = figure.add_subplot(111)
        axis.set_facecolor("#1A1D24")
        axis.tick_params(colors="#C9CED8")
        for subject in sorted({grade.subject for grade in grades})[:8]:
            points = sorted(
                (grade.entered_at, grade.value)
                for grade in grades
                if grade.subject == subject
            )
            if points:
                axis.plot(range(len(points)), [point[1] for point in points], marker="o", label=subject)
        if axis.lines:
            axis.legend(facecolor="#1A1D24", labelcolor="white", fontsize=8)
        axis.grid(True, alpha=0.15)
        self._chart_canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
        self._chart_canvas.draw()
        self._chart_canvas.get_tk_widget().pack(fill="both", expand=True, padx=12, pady=(0, 12))

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
