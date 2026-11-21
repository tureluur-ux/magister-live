from datetime import datetime, timedelta

import requests

from .models import Grade, ScheduleItem


class MagisterApiError(RuntimeError):
    pass


class MagisterApi:
    def __init__(self, school_url: str, access_token: str) -> None:
        self.school_url = school_url.rstrip("/")
        self.access_token = access_token
        self.api_url = self._discover_api_url()
        self.person_id = self._discover_person_id()

    def _discover_api_url(self) -> str:
        try:
            response = requests.get(
                f"{self.school_url}/.well-known/host-meta.json",
                headers={"Authorization": f"Bearer {self.access_token}"},
                timeout=10,
            )
            if response.ok:
                for link in response.json().get("links", []):
                    href = link.get("href")
                    if href:
                        return href.rstrip("/")
        except requests.RequestException:
            pass
        return f"{self.school_url}/api/v1"

    def _get(self, path: str, params: dict | None = None) -> dict:
        response = requests.get(
            f"{self.api_url}{path}",
            params=params,
            headers={"Authorization": f"Bearer {self.access_token}", "Accept": "application/json"},
            timeout=20,
        )
        if response.status_code in (401, 403):
            raise MagisterApiError("TOKEN_EXPIRED")
        if not response.ok:
            raise MagisterApiError(f"Magister antwoordde met status {response.status_code}.")
        return response.json()

    def _discover_person_id(self) -> str:
        try:
            session = self._get("/sessions/current")
            account_href = (session.get("links", {}).get("account", {}) or {}).get("href")
            if account_href:
                account_id = account_href.rstrip("/").split("/")[-1]
                account = self._get(f"/accounts/{account_id}")
                links = account.get("links", {})
                for role in ("leerling", "ouder"):
                    role_link = links.get(role, {})
                    if isinstance(role_link, dict) and role_link.get("href"):
                        return role_link["href"].rstrip("/").split("/")[-1]
        except MagisterApiError:
            pass
        raise MagisterApiError("Het Magister-person-ID kon niet worden gevonden.")

    def grades(self, limit: int = 250) -> list[Grade]:
        data = self._get(
            f"/personen/{self.person_id}/cijfers/laatste",
            {"top": limit, "skip": 0},
        )
        items = data.get("Items") or data.get("items") or []
        grades: list[Grade] = []
        for item in items or []:
            try:
                value = float(str(item.get("waarde")).replace(",", "."))
            except (TypeError, ValueError):
                continue
            vak = item.get("vak") or {}
            grade_id = item.get("kolomId") or item.get("Id")
            grades.append(Grade(
                id=str(grade_id or f"{item.get('ingevoerdOp')}-{vak.get('omschrijving')}"),
                subject=str(vak.get("omschrijving") or vak.get("code") or "Onbekend vak"),
                value=value,
                description=str(item.get("omschrijving") or ""),
                entered_at=str(item.get("ingevoerdOp") or item.get("behaaldOp") or ""),
                weight=float(item.get("weegfactor") or 1),
                sufficient=bool(item.get("isVoldoende", True)),
            ))
        return grades

    def schedule(self, days_ahead: int = 14) -> list[ScheduleItem]:
        start = datetime.now().date()
        end = start + timedelta(days=days_ahead)
        data = self._get(
            f"/personen/{self.person_id}/afspraken",
            {
                "van": start.isoformat(),
                "tot": end.isoformat(),
                "status": 1,
            },
        )
        items = data.get("Items") or []
        return [
            ScheduleItem(
                id=str(item.get("Id") or ""),
                date=str(item.get("Start") or "").split("T")[0],
                start=str(item.get("Start") or ""),
                end=str(item.get("Einde") or ""),
                subject=", ".join(
                    vak.get("Naam") or vak.get("Omschrijving") or ""
                    for vak in (item.get("Vakken") or [])
                ) or "Overig",
                description=str(item.get("Omschrijving") or ""),
                location=str(item.get("Lokatie") or ""),
                teacher=", ".join(
                    teacher.get("Naam") or ""
                    for teacher in (item.get("Docenten") or [])
                ),
                cancelled=int(item.get("Status") or 0) == 2,
                has_homework=bool(item.get("OpdrachtId")),
            )
            for item in items
        ]
