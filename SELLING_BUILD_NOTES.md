# Selling Build Notes

This project can be shared as a packaged executable instead of raw source code.

## What the buyer gets

- macOS: `dist/ScoreboardDashboard`
- Windows: `dist\ScoreboardDashboard.exe`

They run it from terminal, enter the match key, and the dashboard opens in the browser.

## Build on macOS

```bash
chmod +x build_mac.sh
./build_mac.sh
```

Output:

```text
dist/ScoreboardDashboard
```

## Build on Windows

Run this in PowerShell on a Windows machine:

```powershell
.\build_windows.ps1
```

Output:

```text
dist\ScoreboardDashboard.exe
```

## Usage

Interactive:

```bash
./ScoreboardDashboard
```

With match key directly:

```bash
./ScoreboardDashboard 119F
```

Windows:

```powershell
.\ScoreboardDashboard.exe 119F
```

## Important

Windows and macOS need separate executables. PyInstaller normally builds for the OS where it is running, so build the Windows `.exe` on Windows and the macOS binary on macOS.

Packaging hides the normal source files from the buyer, but it is not strong license protection. For selling, add a license agreement, watermark/branding, and optionally a server-side license check.
