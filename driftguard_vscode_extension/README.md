# DriftGuard VS Code Extension

Inline codebase decay warnings from DriftGuard analysis directly in your editor.

## Features

- **Inline Diagnostics**: Red squiggles for CRITICAL files, yellow warnings for AT_RISK files
- **Status Bar**: Shows total issues at a glance (🔴/🟠/🟢)
- **Auto-Refresh**: Automatically updates when new DriftGuard reports are generated
- **Detailed Info**: Hover over diagnostics to see full decay analysis
- **Quick Access**: Click status bar to open the latest report

## Requirements

- DriftGuard must be installed and run in your workspace
- Reports must be generated in the `output/` directory (configurable)

## Usage

1. Run DriftGuard analysis in your workspace:
   ```bash
   python driftguard.py --repo . --days 30
   ```

2. The extension will automatically:
   - Detect the new report
   - Show diagnostics for problematic files
   - Update the status bar

3. Commands:
   - `DriftGuard: Refresh Analysis` - Manually refresh diagnostics
   - `DriftGuard: Open Latest Report` - View the JSON report

## Extension Settings

- `driftguard.reportPath`: Path to DriftGuard output directory (default: `output`)
- `driftguard.autoRefresh`: Automatically refresh when new reports detected (default: `true`)

## How It Works

1. Scans workspace for `output/report_*.json` files
2. Reads the most recent report
3. Creates VS Code diagnostics for CRITICAL and AT_RISK files
4. Shows health scores and recommendations in hover tooltips
5. Watches for new reports and auto-refreshes

## Development

Built for the IBM Bob Dev Day Hackathon 2026.

## License

MIT