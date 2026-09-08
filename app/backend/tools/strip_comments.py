import sys
from pathlib import Path

path = Path(sys.argv[1])
lines = path.read_text().splitlines(keepends=True)
path.write_text("".join(line for line in lines if not line.lstrip().startswith("#")))
