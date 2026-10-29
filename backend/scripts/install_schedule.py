"""Install the weekly updater as a macOS user LaunchAgent (machine must be awake)."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

from backend.scripts.build_player_stats import ROOT


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--deploy', action='store_true', help='Also publish to the linked Vercel project')
    args = parser.parse_args()
    label = 'com.fantasyadvisor.weekly-update'
    path = Path.home() / 'Library/LaunchAgents' / f'{label}.plist'
    log = ROOT / 'reports/weekly-update.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    # launchd uses the Mac's local timezone. Thursday/Monday evening; Sunday before games.
    payload = dict(Label=label, WorkingDirectory=str(ROOT),
                   ProgramArguments=[sys.executable, '-m', 'backend.scripts.update_weekly'] + (['--deploy'] if args.deploy else []),
                   StartCalendarInterval=[dict(Weekday=4, Hour=18, Minute=0), dict(Weekday=0, Hour=12, Minute=0), dict(Weekday=1, Hour=18, Minute=0)],
                   StandardOutPath=str(log), StandardErrorPath=str(log),
                   EnvironmentVariables={'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')})
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        subprocess.run(['launchctl', 'bootout', f'gui/{os.getuid()}', str(path)], check=False)
    path.write_bytes(plistlib.dumps(payload))
    subprocess.run(['launchctl', 'bootstrap', f'gui/{os.getuid()}', str(path)], check=True)
    print(f'Installed {path}: Thu/Mon 6pm, Sun noon, local timezone.')


if __name__ == '__main__':
    main()
