# Magister Live

[![Build and release Windows app](https://github.com/tureluur-ux/magister-live/actions/workflows/build-release.yml/badge.svg)](https://github.com/tureluur-ux/magister-live/actions/workflows/build-release.yml)

Magister Live is een moderne Windows-desktopapp voor cijfers, huiswerk en het rooster. De app gebruikt een browsergebaseerde Magister/OpenID-Connect-login, versleutelde Windows-opslag voor OAuth-tokens en automatische synchronisatie.

## Download

Download `MagisterLive.exe` via de [GitHub Releases-pagina](https://github.com/tureluur-ux/magister-live/releases).
De EXE is standalone en vereist geen geïnstalleerde Python-runtime.

## Inloggen

1. Voer de Magister-school-URL in, bijvoorbeeld `schaersvoorde.magister.net`.
2. Open de officiële Magister/Microsoft-loginpagina in je browser.
3. Meld je aan via je schoolaccount.
4. Magister Live ontvangt de beveiligde logincallback, slaat refresh- en access-tokens versleuteld lokaal op via Windows DPAPI en synchroniseert direct.

Tokens worden automatisch vernieuwd waar de school-OIDC-configuratie dit ondersteunt. Er worden geen Magister-wachtwoorden in JSON opgeslagen.

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

- Browsergebaseerde Magister-login met PKCE en Microsoft Entra-compatibiliteit.
- Versleutelde lokale OAuth-tokenopslag met Windows DPAPI.
- Automatisch tokenverversen.
- Cijfers, gemiddelde per vak en cijferontwikkeling.
- Weekrooster met tijden, lokalen, lessen, annuleringen en huiswerk.
- Synchronisatie bij start en iedere vijf minuten.
- Windows-notificaties bij nieuwe of gewijzigde cijfers.
- Lokale meldinggeschiedenis.
- Excel-export.
- Optioneel starten met Windows en optioneel geluid.
