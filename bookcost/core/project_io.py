"""Import/export of single book projects as JSON files.

The file format is versioned and column-based: unknown columns in a file are
ignored on import and missing ones default to NULL, so files exchanged between
slightly different app versions degrade gracefully instead of failing.
"""

import json

import jdatetime

from bookcost.core.db import DETAIL_COLUMNS, PROJECT_COLUMNS
from bookcost.core.fields import TYPE_FIELD_COLUMNS

FORMAT_NAME = 'shahreqalam-book-project'
FORMAT_VERSION = 2          # v2 adds 'papers' and the series columns

# Proprietary extension for exported projects (double-clickable via the
# installer's file association). The content is plain UTF-8 JSON.
FILE_EXTENSION = '.ketab'


def export_project(db, project_id: int) -> dict:
    """Snapshot of one project as a plain dict. Raises ValueError if missing."""
    project = db.get_project(project_id)
    if not project:
        raise ValueError(f"پروژه‌ای با شناسه {project_id} یافت نشد")
    details = db.get_project_details(project_id)
    project = dict(project)
    details = dict(details) if details else {}
    return {
        'format': FORMAT_NAME,
        'version': FORMAT_VERSION,
        'exported_at': jdatetime.datetime.now().strftime("%Y/%m/%d %H:%M"),
        'project': {c: project.get(c) for c in PROJECT_COLUMNS},
        'details': {c: details.get(c) for c in DETAIL_COLUMNS},
        'papers': db.get_project_papers(project_id),
    }


def import_project(db, data: dict) -> int:
    """Creates a NEW project from an exported dict; returns the new id.

    Raises ValueError on unrecognized data. Type values (paper/print/color/
    zinc names) are registered in `categories` so the combos know them.
    """
    if not isinstance(data, dict) or data.get('format') != FORMAT_NAME:
        raise ValueError("این فایل یک پروژه کتاب معتبر نیست")
    if not isinstance(data.get('project'), dict):
        raise ValueError("فایل پروژه ناقص است")

    src_p = data['project']
    src_d = data.get('details') or {}
    if not src_p.get('title'):
        raise ValueError("فایل پروژه عنوان کتاب ندارد")

    p = {c: src_p.get(c) for c in PROJECT_COLUMNS}
    p.setdefault('creation_date', None)
    p['creation_date'] = p['creation_date'] or jdatetime.date.today().strftime("%Y/%m/%d")
    p['tiraj'] = p.get('tiraj') or 0
    d = {c: src_d.get(c) for c in DETAIL_COLUMNS}

    new_id = db.insert_project(p, d)

    # Multiple paper types (format v2+; older files simply lack the key)
    papers = data.get('papers')
    if isinstance(papers, list):
        valid = [e for e in papers
                 if isinstance(e, dict) and e.get('section') in ('matn', 'jeld')]
        if valid:
            db.replace_project_papers(new_id, valid)

    # Register imported type values so the editable combos list them
    for category, col in TYPE_FIELD_COLUMNS.items():
        value = d.get(col)
        if value:
            db.save_category(category, value)

    return new_id


def save_project_file(db, project_id: int, path: str):
    data = export_project(db, project_id)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_project_file(db, path: str) -> int:
    """Imports a project JSON file; returns the new project id."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as err:
        raise ValueError(f"فایل قابل خواندن نیست:\n{err}") from err
    return import_project(db, data)
