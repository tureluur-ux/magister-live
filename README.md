# Magister Live

[![Build and release Windows app](https://github.com/tureluur-ux/magister-live/actions/workflows/build-release.yml/badge.svg)](https://github.com/tureluur-ux/magister-live/actions/workflows/build-release.yml)

Magister Live is een moderne Windows-desktopapp voor cijfers, huiswerk en het rooster. De app gebruikt de werkende Magister-loginflow en synchroniseert automatisch met je Magister-account.

## Download

Download `MagisterLive.exe` via de [GitHub Releases-pagina](https://github.com/tureluur-ux/magister-live/releases).
De EXE is standalone en vereist geen geïnstalleerde Python-runtime.

## Inloggen

1. Voer de Magister-school-URL in, bijvoorbeeld `schaersvoorde.magister.net`.
2. Vul je Magister-gebruikersnaam in.
3. Vul je wachtwoord in.
4. Magister Live logt in en synchroniseert cijfers, huiswerk en rooster direct.

Het wachtwoord wordt nooit opgeslagen. Alleen school-URL en gebruikersnaam worden lokaal opgeslagen.

## Installatie voor ontwikkeling

Python 3.11 op Windows is vereist.

```powershell
cd magister-notifier
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

## Standalone EXE bouwen

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

De uitvoer staat in `dist\MagisterLive.exe`.

## Functies

- Magister-login via de schooltenant en de officiële Magister-accountlogin.
- Het wachtwoord wordt alleen tijdens het inloggen in het geheugen gebruikt en niet opgeslagen.
- Cijfers, gemiddelde per vak en cijferontwikkeling.
- Weekrooster met tijden, lokalen, lessen, annuleringen en huiswerk.
- Synchronisatie bij start en iedere vijf minuten.
- Windows-notificaties bij nieuwe of gewijzigde cijfers.
- Lokale meldinggeschiedenis.
- Excel-export.
- Optioneel starten met Windows en optioneel geluid.
