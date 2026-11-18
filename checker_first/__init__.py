"""checker-first — checker escrito ANTES, travado e provado nos dois sentidos.

O padrão nasceu no laboratório A/B da casa (jarvis-dungeon): um checker inválido
(mapa sem passagem) reprovou 537 ciclos por 9 horas sem ninguém perceber.
A regra aqui é simples e medida:

  1. Escreva o checker ANTES da tarefa.
  2. Prove que a solução de referência passa 100% (sanidade do fixture).
  3. Prove que o baseline falha (o checker discrimina).
  4. Trav e o checker (modo 444) e não o mostre ao agente.
  5. Só conta medição com `ck=v3`.

Este pacote é agnóstico: não sabe nada de dungeon, de OpenCode nem da casa.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

__version__ = "0.1.0"

SCHEMA = "v3"


@dataclass
class Verdict:
    ck: str
    passed: int
    total: int
    ok: bool
    evidence: str = ""

    def to_dict(self):
        d = asdict(self); d["ok"] = self.ok; return d


def lock_checker(path: str | Path) -> None:
    """Trava o checker contra alteração acidental (444)."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)
    p.chmod(0o444)


def checker_hash(path: str | Path) -> str:
    """Hash do checker travado — toda medição deve carregá-lo."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def run_checker(path: str | Path, cwd: str | Path | None = None, timeout: int = 180) -> Verdict:
    """Roda pytest no checker e devolve veredito com ck."""
    p = Path(path).resolve()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(p)],
                       cwd=str(cwd or p.parent), capture_output=True, text=True,
                       timeout=timeout)
    out = (r.stdout or "") + (r.stderr or "")
    m = None
    for line in out.splitlines():
        if "passed" in line or "failed" in line:
            m = line.strip(); break
    passed = 0; total = 0
    mm = __import__("re").search(r"(\d+) passed", out)
    if mm: passed = int(mm.group(1))
    mf = __import__("re").search(r"(\d+) failed", out)
    failed = int(mf.group(1)) if mf else 0
    total = passed + failed
    return Verdict(SCHEMA, passed, total, r.returncode == 0, (m or out[-200:])[:200])


def prove_two_ways(reference_checker: str | Path, reference_solution: str | Path,
                   baseline: str | Path, timeout: int = 180) -> dict:
    """Prova nos DOIS sentidos: referência passa, baseline falha."""
    import shutil
    tmp = Path(tempfile.mkdtemp(prefix="checker-first-"))
    try:
        area = tmp / "lane"; area.mkdir()
        shutil.copytree(Path(reference_solution).parent, area / "src",
                        dirs_exist_ok=True)
        checker = area / "checker.py"
        shutil.copy(reference_checker, checker)
        lock_checker(checker)
        bom = run_checker(checker, area, timeout)
        # baseline: substitui o arquivo da solução pelo original
        base = Path(baseline)
        if base.is_file():
            shutil.copy(base, area / "src" / base.name)
        ruim = run_checker(checker, area, timeout)
        return {"checker_sha256": checker_hash(checker),
                "referencia": bom.to_dict(), "baseline": ruim.to_dict(),
                "valido": bom.ok and not ruim.ok}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
