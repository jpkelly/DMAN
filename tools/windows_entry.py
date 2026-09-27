"""PyInstaller console entry point. No third-party vendor binaries are loaded."""
import sys
import traceback
from pathlib import Path

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dsan_display.windows import main


def pause_on_error():
    if getattr(sys, 'frozen', False) and sys.stdin and sys.stdin.isatty():
        try:
            input('Press Enter to close. ')
        except (EOFError, KeyboardInterrupt):
            pass


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        if exc.code:
            pause_on_error()
        raise
    except Exception:
        traceback.print_exc()
        pause_on_error()
        raise SystemExit(1)
