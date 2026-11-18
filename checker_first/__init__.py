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
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path

__version__ = "0.1.1"

SCHEMA = "v3"

# Os três estados possíveis do instrumento. O caso real do lab (v0.1.0 não o
# distinguia) era o do meio: um checker IMPOSSIVEL reprovava a referência E o
# baseline, e a série inteira morria achando que o modelo era o culpado.
#
#   ok              o instrumento distingue: referência passa, baseline falha
#   fixture_invalido a REFERENCIA falhou: o cenário é impossível (o caso de
#                   537 ciclos). Não é problema de modelo, é problema do
#                   instrumento. Pare a série.
#   nao_discrimina  a referência passou e o baseline TAMBÉM passou: o checker
#                   não separa nada. Ele mede, mas não discrimina.
VERDICT_OK = "ok"
VERDICT_FIXTURE_INVALIDO = "fixture_invalido"
VERDICT_NAO_DISCRIMINA = "nao_discrimina"


@dataclass
class Verdict:
    ck: str
    passed: int
    total: int
    ok: bool
    evidence: str = ""

    def to_dict(self):
        d = asdict(self); d["ok"] = self.ok; return d


@dataclass
class Report:
    """O diagnóstico do instrumento, com o nome do defeito e o que fazer."""

    verdict: str
    ck: str
    checker_sha256: str
    referencia: dict
    baseline: dict
    diagnostico: str
    acao: str

    def to_dict(self):
        return asdict(self)

    @property
    def ok(self) -> bool:
        return self.verdict == VERDICT_OK


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
    mm = re.search(r"(\d+) passed", out)
    if mm: passed = int(mm.group(1))
    mf = re.search(r"(\d+) failed", out)
    failed = int(mf.group(1)) if mf else 0
    total = passed + failed
    return Verdict(SCHEMA, passed, total, r.returncode == 0, (m or out[-200:])[:200])


def _pytest_output(path: str | Path, cwd: str | Path | None = None,
                   timeout: int = 180) -> str:
    """A saída crua do pytest: é dela que sai o sinal de 'ninguém passa'."""
    p = Path(path).resolve()
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", str(p)],
                       cwd=str(cwd or p.parent), capture_output=True, text=True,
                       timeout=timeout)
    return (r.stdout or "") + (r.stderr or "")


def diagnose(reference: Verdict, baseline: Verdict) -> tuple[str, str, str]:
    """Distingue os TRÊS estados do instrumento.

    O v0.1.0 devolvia só `valido: bool`. Com isso, um checker IMPOSSÍVEL
    (referência falha) e um checker FRACO (baseline passa) davam a mesma
    resposta, e o time não sabia qual dos dois estava olhando.
    """
    if not reference.ok:
        return (
            VERDICT_FIXTURE_INVALIDO,
            "A referência tambem reprovou. O cenario e' IMPOSSIVEL (ou a "
            "solucao de referencia esta errada): todo mundo vai reprovar e a "
            "serie vai medir o instrumento, nao o modelo.",
            "PARE a serie. Corrija o cenario ou a referencia e rode o doctor "
            "de novo. Nao comecoe a medir antes disso.",
        )
    if baseline.ok:
        return (
            VERDICT_NAO_DISCRIMINA,
            "A referencia passou e o baseline tambem. O checker nao separa "
            "nada: ele mede, mas nao discrimina.",
            "Aumente a exigencia do checker (comportamento observavel) ate "
            "ele reprovar o baseline, e rode o doctor de novo.",
        )
    return (
        VERDICT_OK,
        "O instrumento distingue: a referencia passa e o baseline falha.",
        "Pode medir. Guarde o ck=v3 e o hash do checker em toda medicao.",
    )


def _write_conftest(area: Path) -> None:
    """O `conftest.py` que coloca `src/` no path do pytest.

    (18/11, v0.1.1) Sem isso, um checker que importa o modulo do projeto
    (`from mapa import Mapa`) falha na COLETA com `ModuleNotFoundError`, e
    o veredito sai como "a referencia reprovou" — ou seja, o doctor acusaria
    `fixture_invalido` num cenario perfectly possivel. O lab ja sabia
    disso: o `ab_loop.sh` escreve o mesmo conftest na lane. Aqui o problema
    e' do PACOTE, e por isso a correcao e' no pacote e nao no teste.
    """
    (area / "conftest.py").write_text(
        "import os, sys\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))\n",
        encoding="utf-8")


def _write_conftest(area: Path) -> None:
    """O `conftest.py` que coloca o `src/` no path.

    Sem isto, um checker que importa o modulo do projeto (`from mapa import
    Mapa`) reprova com ImportError na COLETA, e o doctor le isso como
    "referencia reprovou" — ou seja, acusaria fixture invalido num
    instrumento que esta perfeitamente bom. O laboratorio A/B resolve isso
    com um conftest.py na lane; aqui o proprio doctor cria um, porque o
    pacote nao pode exigir que quem usa saiba desse detalhe.
    """
    (area / "conftest.py").write_text(
        "import os, sys\n"
        "sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))\n",
        encoding="utf-8")


def _apply_baseline(area: Path, reference_solution: Path, baseline: Path) -> str:
    """Troca a referência pelo baseline NO LUGAR CERTO.

    (18/11, v0.1.1) BUG REAL do v0.1.0: o baseline era copiado para
    `src/<nome-do-arquivo-do-baseline>`. Se o checker importa o modulo pelo
    nome da referencia (que e o normal: `from mapa import Mapa`), o arquivo
    novo fica ao lado e **nada muda** — a rodada do "baseline" rodava a
    referencia de novo. Consequencia medida: o `verify` devolvia
    `valido: false` com o baseline PASSANDO, e o `doctor` acusava
    `nao_discrimina` num instrumento bom. Agora o baseline substitui o
    arquivo pelo NOME DA REFERENCIA, que e o que o codigo do projeto
    importa.
    """
    nome = reference_solution.name
    destino = area / "src" / nome
    if baseline.is_file():
        shutil.copy(baseline, destino)
        return nome
    # o baseline nao tem o mesmo nome: usa o conteudo dele no lugar certo
    if destino.is_file():
        destino.write_text(baseline.read_text(encoding="utf-8"), encoding="utf-8")
        return nome
    return ""


def prove_two_ways(reference_checker: str | Path, reference_solution: str | Path,
                   baseline: str | Path, timeout: int = 180) -> dict:
    """Prova nos DOIS sentidos: referência passa, baseline falha.

    Mantido com o formato antigo (chave `valido`) por compatibilidade; a
    v0.1.1 acrescenta `diagnostico` e `verdict`, que dizem QUAL dos dois
    defeitos aconteceu.
    """
    import shutil
    tmp = Path(tempfile.mkdtemp(prefix="checker-first-"))
    try:
        area = tmp / "lane"; area.mkdir()
        shutil.copytree(Path(reference_solution).parent, area / "src",
                        dirs_exist_ok=True)
        _write_conftest(area)
        checker = area / "checker.py"
        shutil.copy(reference_checker, checker)
        lock_checker(checker)
        bom = run_checker(checker, area, timeout)
        # baseline: substitui o arquivo da solução pelo original
        base = Path(baseline)
        _apply_baseline(area, Path(reference_solution), base)
        ruim = run_checker(checker, area, timeout)
        verdict, diagnostico, acao = diagnose(bom, ruim)
        return {"checker_sha256": checker_hash(checker),
                "referencia": bom.to_dict(), "baseline": ruim.to_dict(),
                "valido": bom.ok and not ruim.ok,
                "verdict": verdict,
                "diagnostico": diagnostico,
                "acao": acao}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def doctor(reference_checker: str | Path, reference_solution: str | Path,
           baseline: str | Path, timeout: int = 180) -> Report:
    """O `doctor`: diagnostica o instrumento e diz se a serie pode comecar.

    É o passo que faltava na v0.1.0. O caso real do lab: um checker que
    exigia um mapa sem passagem reprovou 537 ciclos em 9 horas. Nenhum passo
    da prova em dois sentidos acusava isso, porque a prova só olhava se o
    baseline falhava — e o baseline falhava, sim, o tempo todo.
    """
    import shutil
    tmp = Path(tempfile.mkdtemp(prefix="checker-first-doctor-"))
    try:
        area = tmp / "lane"; area.mkdir()
        shutil.copytree(Path(reference_solution).parent, area / "src",
                        dirs_exist_ok=True)
        _write_conftest(area)
        checker = area / "checker.py"
        shutil.copy(reference_checker, checker)
        lock_checker(checker)
        out_ref = _pytest_output(checker, area, timeout)
        bom = run_checker(checker, area, timeout)
        base = Path(baseline)
        _apply_baseline(area, Path(reference_solution), base)
        ruim = run_checker(checker, area, timeout)
        verdict, diagnostico, acao = diagnose(bom, ruim)
        # a evidência do caso real: quando a referência reprova, o pytest
        # mostra que é o FIXTURE, não o código. Guardamos as linhas que
        # nomeiam o teste que reprovou, para o time ver o defeito.
        evidencia = bom.evidence
        if verdict == VERDICT_FIXTURE_INVALIDO:
            falhas = [l.strip() for l in out_ref.splitlines()
                      if l.startswith("FAILED") or "Error" in l][:5]
            evidencia = (bom.evidence + " | " + " ; ".join(falhas))[:300]
        return Report(verdict=verdict, ck=SCHEMA,
                      checker_sha256=checker_hash(checker),
                      referencia=bom.to_dict(), baseline=ruim.to_dict(),
                      diagnostico=diagnostico, acao=acao)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
