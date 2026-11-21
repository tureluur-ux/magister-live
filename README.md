# Magister Notifier

[![Build and release Windows app](https://github.com/tureluur-ux/magister-notifier/actions/workflows/build-release.yml/badge.svg)](https://github.com/tureluur-ux/magister-notifier/actions/workflows/build-release.yml)

Een moderne Windows-desktopapp in Python voor het volgen van cijfers, huiswerk en het rooster via Magister.

## Download

Download `MagisterNotifier.exe` vanaf de [GitHub Releases-pagina](https://github.com/tureluur-ux/magister-notifier/releases).
De EXE is een zelfstandige Windows-applicatie en vereist geen geïnstalleerde Python-runtime.

## Installatie voor ontwikkeling

Voorwaarde: Python 3.11 op Windows.

```powershell
cd magister-notifier
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

Het wachtwoord wordt niet opgeslagen. Schoolnaam en gebruikersnaam worden lokaal opgeslagen in `%LOCALAPPDATA%\magister_notifier\data.json`.

## Standalone EXE bouwen

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

De uitvoer staat in `dist\MagisterNotifier.exe`. De EXE kan direct worden gekopieerd naar een andere Windows-PC; Windows hoeft Python niet te hebben.

## Functies

- Inloggen met MagisterPy.
- Cijfers, rooster en opdrachten ophalen.
- Automatische synchronisatie elke vijf minuten.
- Windows-meldingen en optioneel geluid.
- Lokale meldinggeschiedenis.
- Gemiddelden per vak.
- Cijfergrafiek.
- Excel-export.
- Optioneel starten met Windows.
