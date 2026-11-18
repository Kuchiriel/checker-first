"""O CASO REAL DO LAB, como teste.

O que aconteceu no laboratorio A/B da casa (jarvis-dungeon, 16-17/11):
um checker de pathfinding exigia que o inimigo contornasse uma parede
INTERNA que, no fixture, tapava o mapa inteiro. A passagem nao existia.
O resultado: **537 ciclos e 9 horas** de medicao, e todo mundo reprovava.
Nenhum modelo era o culpado: o **instrumento** era impossivel.

O v0.1.0 do checker-first provava que a referencia passa e o baseline falha.
Com um checker IMPOSSIVEL, o baseline falhava (ok) e a referencia TAMBEM
falhava — e a prova devolvia `valido: false` sem dizer QUAL dos dois
defeitos era. O time via "o checker nao esta bom" e seguia medindo.

Este teste usa o **mesmo defeito, sem o dungeon**: um mapa 5x5 com uma
parede que fecha o caminho e um checker que exige o caminho.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import checker_first as cf


# ── o cenario impossivel (o defeito real do lab, generico) ──────────────

MAPA = {
    # um mapa 5x5; a parede em X fecha o corredor INTEIRO (passagem
    # inexistente): e o que o lab tinha.
    "mapa.py": '''
class Mapa:
    def __init__(self, cols=5, rows=5):
        self.cols, self.rows = cols, rows
        self.bloqueado = {(2, y) for y in range(rows)}

    def livre(self, x, y):
        return 0 <= x < self.cols and 0 <= y < self.rows and (x, y) not in self.bloqueado

    def caminho(self, inicio, fim):
        """Busca em largura. Com a parede fechando, nao ha caminho."""
        from collections import deque
        fila, visto = deque([inicio]), {inicio}
        while fila:
            at = fila.popleft()
            if at == fim:
                return True
            for viz in ((at[0]+1, at[1]), (at[0]-1, at[1]),
                        (at[0], at[1]+1), (at[0], at[1]-1)):
                if viz in visto or not self.livre(*viz):
                    continue
                visto.add(viz); fila.append(viz)
        return False
''',
}

# a versao POSSIVEL (o cenario depois de corrigido): a parede deixa uma fresta
MAPA_CORRIGIDO = {
    "mapa.py": '''
class Mapa:
    def __init__(self, cols=5, rows=5):
        self.cols, self.rows = cols, rows
        self.bloqueado = {(2, y) for y in range(rows) if y != 2}

    def livre(self, x, y):
        return 0 <= x < self.cols and 0 <= y < self.rows and (x, y) not in self.bloqueado

    def caminho(self, inicio, fim):
        from collections import deque
        fila, visto = deque([inicio]), {inicio}
        while fila:
            at = fila.popleft()
            if at == fim:
                return True
            for viz in ((at[0]+1, at[1]), (at[0]-1, at[1]),
                        (at[0], at[1]+1), (at[0], at[1]-1)):
                if viz in visto or not self.livre(*viz):
                    continue
                visto.add(viz); fila.append(viz)
        return False
''',
}

# o checker: exige que o caminho exista (o comportamento, sem nome de metodo)
CHECKER = '''
from mapa import Mapa

def test_cenario_tem_passagem():
    """A sanidade do fixture: o cenario e' POSSIVEL? (a regra 2 do lab)"""
    assert Mapa().caminho((0, 2), (4, 2)), "fixture sem passagem"

def test_caminho_existe():
    assert Mapa().caminho((0, 2), (4, 2))
'''


def _area(tmp: Path, mapa: dict) -> Path:
    src = tmp / "src"
    src.mkdir(parents=True, exist_ok=True)
    for nome, corpo in mapa.items():
        (src / nome).write_text(corpo, encoding="utf-8")
    (tmp / "checker.py").write_text(CHECKER, encoding="utf-8")
    return tmp


def test_checker_impossivel_e_acusado_pelo_doctor():
    """O CASO REAL: o cenario e' impossivel e o doctor tem de dizer isso.

    Sem este teste, o lab perde 537 ciclos achando que o modelo e' o culpado.
    """
    tmp = Path(tempfile.mkdtemp(prefix="cf-real-"))
    try:
        area = _area(tmp / "impossivel", MAPA)
        ref = area / "src" / "mapa.py"
        (area / "baseline.py").write_text(
            "class Mapa:\n    def caminho(self, a, b):\n        return False\n",
            encoding="utf-8")
        r = cf.doctor(area / "checker.py", ref, area / "baseline.py")
        assert r.verdict == cf.VERDICT_FIXTURE_INVALIDO, r.verdict
        assert not r.ok
        # o diagnostico tem de NOMBRAR o defeito e dizer para parar
        assert "IMPOSSIVEL" in r.diagnostico
        assert "PARE" in r.acao
        # e o caso tem de ser distinguivel do outro defeito
        assert r.verdict != cf.VERDICT_NAO_DISCRIMINA
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_checker_fraco_e_acusado_de_outro_jeito():
    """O outro defeito: o checker nao discrimina (baseline tambem passa)."""
    tmp = Path(tempfile.mkdtemp(prefix="cf-fraco-"))
    try:
        area = _area(tmp / "fraco", MAPA_CORRIGIDO)
        ref = area / "src" / "mapa.py"
        (area / "baseline.py").write_text(
            "class Mapa:\n"
            "    def __init__(self, cols=5, rows=5):\n"
            "        self.bloqueado = {(2, y) for y in range(rows) if y != 2}\n"
            "    def livre(self, x, y):\n"
            "        return 0 <= x < self.cols and 0 <= y < self.rows\n"
            "    def caminho(self, a, b):\n"
            "        return True\n",
            encoding="utf-8")
        r = cf.doctor(area / "checker.py", ref, area / "baseline.py")
        assert r.verdict == cf.VERDICT_NAO_DISCRIMINA, r.verdict
        assert "nao separa" in r.diagnostico
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_instrumento_valido_passa_no_doctor():
    """O caminho feliz: cenario possivel, referencia passa, baseline falha."""
    tmp = Path(tempfile.mkdtemp(prefix="cf-ok-"))
    try:
        area = _area(tmp / "ok", MAPA_CORRIGIDO)
        ref = area / "src" / "mapa.py"
        # o baseline: o MESMO mapa possivel, mas o `caminho` mente e diz
        # que nao ha caminho (e o que o agente faz antes de consertar).
        # Se ele usasse um `livre` sem bloqueios, o baseline acharia o
        # caminho e passaria — e o teste mediria o teste, nao o checker.
        (area / "baseline.py").write_text(
            "class Mapa:\n"
            "    def __init__(self, cols=5, rows=5):\n"
            "        self.bloqueado = {(2, y) for y in range(rows) if y != 2}\n"
            "    def livre(self, x, y):\n"
            "        return 0 <= x < self.cols and 0 <= y < self.rows \\\n"
            "            and (x, y) not in self.bloqueado\n"
            "    def caminho(self, a, b):\n"
            "        return False\n",
            encoding="utf-8")
        r = cf.doctor(area / "checker.py", ref, area / "baseline.py")
        assert r.verdict == cf.VERDICT_OK, (r.verdict, r.diagnostico)
        assert r.ok
        assert r.ck == "v3"
        assert len(r.checker_sha256) == 16
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
