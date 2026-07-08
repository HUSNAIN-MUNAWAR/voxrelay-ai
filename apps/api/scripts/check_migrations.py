from __future__ import annotations

from pathlib import Path

versions = sorted(Path(__file__).resolve().parents[1].joinpath('alembic/versions').glob('*.py'))
print('migration_files=', len(versions))
for path in versions:
    print(path.name)
