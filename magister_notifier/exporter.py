from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from .models import Grade


def export_grades(grades: list[Grade], path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Cijfers"
    headers = ["Vak", "Cijfer", "Omschrijving", "Datum", "Weegfactor", "Voldoende"]
    sheet.append(headers)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for grade in sorted(grades, key=lambda item: item.entered_at, reverse=True):
        sheet.append([
            grade.subject,
            grade.value,
            grade.description,
            grade.entered_at,
            grade.weight,
            "Ja" if grade.sufficient else "Nee",
        ])
    for column in sheet.columns:
        max_length = max(len(str(cell.value or "")) for cell in column)
        column_letter = column[0].column_letter
        sheet.column_dimensions[column_letter].width = min(max_length + 2, 60)
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top")
    workbook.save(path)
