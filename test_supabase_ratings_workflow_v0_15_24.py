# -*- coding: utf-8 -*-
"""Static regression checks for the v0.15.24 Supabase ratings Action."""
from pathlib import Path


def main() -> int:
    path = Path('.github/workflows/supabase_ratings_sync.yml')
    text = path.read_text(encoding='utf-8')
    required = {
        'schedule': 'cron: "12,42 * * * *"',
        'manual full sync': 'workflow_dispatch:',
        'full input': 'full:',
        'write permission': 'contents: write',
        'shared archive lock': 'group: inversion-archive-writer',
        'secret key': 'SUPABASE_SECRET_KEY',
        'legacy secret fallback': 'SUPABASE_SERVICE_ROLE_KEY',
        'rating regression': 'python test_supabase_ratings_sync_v0_15_24.py',
        'sync command': 'python sync_supabase_ratings.py',
        'full flag': 'ARGS+=(--full)',
        'ratings-only staging': 'git add archive/ratings',
        'rebase before push': 'git pull --rebase origin main',
        'push': 'git push',
    }
    missing = [name for name, needle in required.items() if needle not in text]
    if missing:
        raise AssertionError('Workflow-Bestandteile fehlen: ' + ', '.join(missing))

    collector = Path('.github/workflows/inversion_collect.yml').read_text(encoding='utf-8')
    if 'group: inversion-archive-writer' not in collector:
        raise AssertionError('Wetter-/KIT-Collector benutzt nicht dieselbe Archive-Concurrency-Gruppe')
    if 'git pull --rebase origin main' not in collector:
        raise AssertionError('Wetter-/KIT-Collector rebased nicht vor dem Push')

    print('test_supabase_ratings_workflow_v0_15_24: PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
