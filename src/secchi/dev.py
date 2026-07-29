"""Dev entry point — bypasses argparse for use with `textual run --dev`.

Usage:
    uv run textual run --dev src/secchi/dev.py -- -p tuffcli
"""

import sys

from secchi.config import find_config, load_project
from secchi.ui.app import Secchi

project_name = "tuffcli"

# parse optional --project / -p from sys.argv manually
args = sys.argv[1:]
for i, arg in enumerate(args):
    if arg in ("--project", "-p") and i + 1 < len(args):
        project_name = args[i + 1]
        break

config_path = find_config(None)
if not config_path:
    print("No config file found.")
    sys.exit(1)

try:
    project = load_project(config_path, project_name)
except ValueError as e:
    print(f"Error: {e}")
    sys.exit(1)

app = Secchi(project=project, config_path=config_path)
app.run()
