#!/usr/bin/env python3
"""Lab studies - group captures into one roll-up conclusion (#159, epic #153).

A *study* is the cross-experiment synthesis on top of per-experiment notes (#158):
the "we thought X, tried Y1/Y2/Y3, concluded Z" record. It names a set of member
captures, carries a study-level thesis + roll-up conclusion, and shows the members
side-by-side. Per ADR-0017's tracked-path principle (which deferred this decision to
#159), a study persists durably to the *tracked* ``docs/experiments/studies/<id>.json``
- so the synthesis is backed up by a commit, just like the notes.

serve.py serves the catalog at ``/lab/studies`` and a study at ``/lab/study/<id>``;
``POST /lab/study/<id>`` saves it. Read-only on the captures themselves.
"""

from __future__ import annotations

import html
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parents[1]
_EXPERIMENTS = _REPO / "experiments"
_STUDIES = _REPO / "docs" / "experiments" / "studies"
_TEMPLATE = _HERE / "lab_studies_template.html"
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")  # no traversal from the URL
_FIELDS = ("name", "subject", "thesis", "conclusion")

if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from dashboard import FONTS_CSS, TOKENS_CSS  # noqa: E402  (one token source)
from lab_notes import load_notes  # noqa: E402  (per-experiment conclusions, #158)
from parse_v1 import parse_files  # noqa: E402


def _study_path(sid: str, studies_dir: str | Path | None) -> Path | None:
    if not _ID_RE.match(sid) or ".." in sid:
        return None
    root = Path(studies_dir) if studies_dir else _STUDIES
    return root / f"{sid}.json"


def _norm_members(val: object) -> list[str]:
    """Members as a clean, unique list of valid experiment ids (accepts a list or a
    comma/space/newline string from the editor)."""
    if isinstance(val, str):
        parts: list[str] = re.split(r"[\s,]+", val.strip())
    elif isinstance(val, list):
        parts = [str(x) for x in val]
    else:
        parts = []
    out: list[str] = []
    for p in (s.strip() for s in parts):
        if p and _ID_RE.match(p) and ".." not in p and p not in out:
            out.append(p)
    return out


def load_study(sid: str, studies_dir: str | Path | None = None) -> dict | None:
    """A study record, or None if it doesn't exist / is unreadable."""
    p = _study_path(sid, studies_dir)
    if p is None or not p.exists():
        return None
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return doc if isinstance(doc, dict) else None


def list_studies(studies_dir: str | Path | None = None) -> list[dict]:
    """Every study, newest first. Degrades gracefully on a bad file (skipped)."""
    root = Path(studies_dir) if studies_dir else _STUDIES
    if not root.exists():
        return []
    out: list[dict] = []
    for f in root.glob("*.json"):
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(doc, dict):
            doc.setdefault("study_id", f.stem)
            out.append(doc)
    out.sort(key=lambda s: s.get("saved_at") or "", reverse=True)
    return out


def save_study(sid: str, fields: dict, studies_dir: str | Path | None = None) -> dict:
    """Create or update a study; bump ``version`` and stamp ``saved_at`` (UTC).

    Writes the working-tree file; the commit is the backup (ADR-0017 §5)."""
    p = _study_path(sid, studies_dir)
    if p is None:
        raise ValueError(f"invalid study id: {sid!r}")
    doc: dict = load_study(sid, studies_dir) or {}
    for k in _FIELDS:
        if k in fields:
            doc[k] = str(fields[k])
        doc.setdefault(k, "")
    if "members" in fields:
        doc["members"] = _norm_members(fields["members"])
    doc.setdefault("members", [])
    doc["study_id"] = sid
    doc["version"] = int(doc.get("version", 0) or 0) + 1
    doc["saved_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8", newline="\n")
    return doc


def _member_median(eid: str, experiments_dir: Path) -> int | None:
    """The member capture's overall raw-ADC median, or None (cheap headline stat)."""
    csv = experiments_dir / eid / f"{eid}.csv"
    if not csv.exists():
        return None
    try:
        vals = [
            r.raw_value
            for r in parse_files([str(csv)]).readings
            if r.record_type.startswith("plants.soil") and r.raw_value is not None
        ]
        return round(statistics.median(vals)) if vals else None
    except Exception:  # a corrupt capture must not break the study view
        return None


def _member_card(eid: str, experiments_dir: Path) -> str:
    """One member capture, side-by-side: title (-> its detail), subject, headline
    median, and its per-experiment conclusion (the synthesis input)."""
    esc = html.escape
    exp = experiments_dir / eid
    manifest = exp / "manifest.json"
    title, subject = eid, None
    if manifest.exists():
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
            title = m.get("title") or m.get("subject") or eid
            subject = m.get("subject")
        except (json.JSONDecodeError, OSError):
            pass
    elif not exp.is_dir():
        return (
            f'<article class="mcard missing"><div class="mh">{esc(eid)}</div>'
            '<div class="mmeta">capture not found locally</div></article>'
        )
    med = _member_median(eid, experiments_dir)
    med_s = f"median ~{med}" if med is not None else "median —"
    concl = (load_notes(eid).get("conclusion") or "").strip()
    concl_html = (
        f'<p class="mconcl">{esc(concl)}</p>'
        if concl
        else '<p class="mconcl empty">no conclusion noted yet</p>'
    )
    sub_html = f'<span class="msub">{esc(str(subject))}</span>' if subject else ""
    return (
        f'<article class="mcard"><div class="mh">'
        f'<a href="/lab/{esc(eid)}">{esc(str(title))}</a></div>'
        f'<div class="mmeta">{sub_html}<span class="mstat">{esc(med_s)}</span></div>'
        f"{concl_html}</article>"
    )


def _shell(title: str, content: str) -> str:
    template = _TEMPLATE.read_text(encoding="utf-8")
    tokens = TOKENS_CSS.read_text(encoding="utf-8") if TOKENS_CSS.exists() else ""
    fonts = FONTS_CSS.read_text(encoding="utf-8") if FONTS_CSS.exists() else ""
    return (
        template.replace("/*__SPROUT_TOKENS__*/", fonts + "\n" + tokens)
        .replace("<!--__TITLE__-->", html.escape(title))
        .replace("<!--__CONTENT__-->", content)
    )


def render_studies_catalog(studies: list[dict]) -> str:
    """The /lab/studies page: every study as a card + a "new study" form."""
    esc = html.escape
    if studies:
        cards = "\n".join(
            f'<a class="scard" href="/lab/study/{esc(str(s.get("study_id", "")))}">'
            f'<div class="sh"><h3>{esc(str(s.get("name") or s.get("study_id")))}</h3>'
            f'<span class="scount">{len(s.get("members") or [])} captures</span></div>'
            f'<p class="sthesis">{esc(str(s.get("thesis") or "no thesis yet"))}</p></a>'
            for s in studies
        )
    else:
        cards = '<p class="empty">No studies yet — name one below to start.</p>'
    content = f"""
  <div class="top">
    <div><h1>🌱 Studies</h1>
      <div class="sub">{len(studies)} study(ies) · group captures</div></div>
    <a class="back" href="/lab">← experiments</a>
  </div>
  <div class="scards">{cards}</div>
  <form class="newstudy" id="newstudy">
    <input id="sname" type="text" placeholder="New study name" maxlength="80" required>
    <button type="submit" class="nbtn">Create study</button>
  </form>
  <script>
    document.getElementById("newstudy").addEventListener("submit", function (e) {{
      e.preventDefault();
      var name = document.getElementById("sname").value.trim();
      if (!name) return;
      var sid = name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
      if (!sid) return;
      fetch("/lab/study/" + encodeURIComponent(sid), {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ name: name }}),
      }}).then(function () {{ location.href = "/lab/study/" + sid; }});
    }});
  </script>"""
    return _shell("Studies", content)


def render_study_detail(
    sid: str,
    studies_dir: str | Path | None = None,
    experiments_dir: str | Path | None = None,
) -> str | None:
    """The /lab/study/<id> page, or None if the study doesn't exist (-> 404)."""
    s = load_study(sid, studies_dir)
    if s is None:
        return None
    esc = html.escape
    exp_root = Path(experiments_dir) if experiments_dir else _EXPERIMENTS
    members = s.get("members") or []
    member_html = (
        "".join(_member_card(eid, exp_root) for eid in members)
        if members
        else '<p class="empty">No member captures yet — add their ids below.</p>'
    )
    ver = s.get("version") or 0
    saved = f"saved {esc(str(s.get('saved_at')))} · v{ver}" if ver else "not saved yet"
    sid_e = esc(sid)
    name = esc(str(s.get("name") or sid))
    subj = esc(str(s.get("subject") or ""))
    thesis = esc(str(s.get("thesis") or ""))
    concl = esc(str(s.get("conclusion") or ""))
    members_text = esc(chr(10).join(members))
    content = f"""
  <div class="top">
    <div><h1>{name}</h1>
      <div class="sub">{subj} · study · {len(members)} captures</div></div>
    <a class="back" href="/lab/studies">← studies</a>
  </div>
  <section class="study" id="study" data-sid="{sid_e}">
    <div class="srow"><label><span>Subject</span>
      <input id="f-subject" type="text" value="{subj}"></label></div>
    <label class="block">
      <span>Thesis — what this study set out to test</span>
      <textarea id="f-thesis" rows="2">{thesis}</textarea></label>
    <label class="block">
      <span>Roll-up conclusion — what the members concluded together</span>
      <textarea id="f-conclusion" rows="3">{concl}</textarea></label>
    <label class="block">
      <span>Members — experiment ids (comma or newline separated)</span>
      <textarea id="f-members" rows="2">{members_text}</textarea></label>
    <div class="sactions">
      <button id="ssave" class="nbtn" type="button">Save study</button>
      <span class="saved" id="ssaved">{saved}</span>
      <span class="nhint">writes
        <code>docs/experiments/studies/{sid_e}.json</code> · commit to back up</span>
    </div>
  </section>
  <h2 class="mtitle">Members side-by-side</h2>
  <div class="mcards">{member_html}</div>
  <script>
    (function () {{
      var sid = document.getElementById("study").dataset.sid;
      var btn = document.getElementById("ssave");
      var saved = document.getElementById("ssaved");
      btn.addEventListener("click", function () {{
        var body = {{
          subject: document.getElementById("f-subject").value,
          thesis: document.getElementById("f-thesis").value,
          conclusion: document.getElementById("f-conclusion").value,
          members: document.getElementById("f-members").value,
        }};
        btn.disabled = true; btn.textContent = "Saving…";
        fetch("/lab/study/" + encodeURIComponent(sid), {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(body),
        }})
          .then(function (r) {{ return r.json(); }})
          .then(function () {{ location.reload(); }})
          .catch(function () {{
            saved.textContent = "save failed";
            btn.disabled = false; btn.textContent = "Save study";
          }});
      }});
    }})();
  </script>"""
    return _shell(str(s.get("name") or sid), content)
