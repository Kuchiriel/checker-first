#!/usr/bin/env python3
"""checker-first CLI + API local (stdlib, sem dependências)."""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import checker_first as cf


def print_json(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def api(port: int, bind: str):
    class H(BaseHTTPRequestHandler):
        def _send(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers(); self.wfile.write(b)

        def do_GET(self):
            if self.path in ("/health", "/"):
                return self._send(200, {"ok": True, "service": "checker-first",
                                        "version": cf.__version__, "ck": cf.SCHEMA})
            if self.path == "/contract":
                return self._send(200, {"ck": cf.SCHEMA,
                    "rule": ["write_checker_before", "prove_reference_passes",
                             "prove_baseline_fails", "lock_444", "ck_v3_only"],
                    "verdicts": [cf.VERDICT_OK, cf.VERDICT_FIXTURE_INVALIDO,
                                 cf.VERDICT_NAO_DISCRIMINA]})
            self._send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/verify":
                return self._send(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                d = json.loads(self.rfile.read(n) or b"{}")
                if d.get("mode") == "doctor":
                    r = cf.doctor(d["checker"], d["reference"], d["baseline"]).to_dict()
                else:
                    r = cf.prove_two_ways(d["checker"], d["reference"], d["baseline"])
                self._send(200, r)
            except Exception as e:
                self._send(400, {"error": f"{type(e).__name__}: {e}"})

        def log_message(self, *a): pass

    print(f"checker-first API em http://{bind}:{port} — ctrl+c para parar")
    ThreadingHTTPServer((bind, port), H).serve_forever()


def main():
    p = argparse.ArgumentParser(prog="checker-first", description=__doc__)
    p.add_argument("--version", action="version", version=cf.__version__)
    sub = p.add_subparsers(dest="cmd")
    q = sub.add_parser("hash", help="hash de um checker travado")
    q.add_argument("path")
    q = sub.add_parser("run", help="roda checker e mostra veredito ck=v3")
    q.add_argument("path"); q.add_argument("--cwd")
    q = sub.add_parser("verify", help="prova nos 2 sentidos")
    q.add_argument("--checker", required=True); q.add_argument("--reference", required=True)
    q.add_argument("--baseline", required=True)
    q = sub.add_parser("doctor", help="diagnostica o instrumento e diz se a serie pode comecar")
    q.add_argument("--checker", required=True); q.add_argument("--reference", required=True)
    q.add_argument("--baseline", required=True)
    q = sub.add_parser("api", help="sobe API OpenAI-agnostica local")
    q.add_argument("--port", type=int, default=8790)
    q.add_argument("--bind", default="127.0.0.1")
    a = p.parse_args()
    if a.cmd == "hash":
        print(cf.checker_hash(a.path))
    elif a.cmd == "run":
        print_json(cf.run_checker(a.path, a.cwd).to_dict())
    elif a.cmd == "verify":
        print_json(cf.prove_two_ways(a.checker, a.reference, a.baseline))
    elif a.cmd == "doctor":
        rep = cf.doctor(a.checker, a.reference, a.baseline)
        print_json(rep.to_dict())
        # o codigo de saida diz se a serie pode comecar: 0 so quando o
        # instrumento e' valido. Um script de serie que ignora isto volta a
        # medir o instrumento em vez do modelo (o caso de 537 ciclos).
        return 0 if rep.ok else 1
    elif a.cmd == "api":
        api(a.port, a.bind)
    else:
        print("use: checker-first hash|run|verify|doctor|api")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
