# checker-first

**Checker escrito antes, travado e provado nos dois sentidos.**

Padrão extraído do laboratório A/B da casa, onde 9 horas e 537 ciclos foram
perdidos porque um checker pedia um mapa impossível — e todo mundo reprovava.
A correção não foi um modelo melhor: foi **validar o instrumento antes de medir**.

## Regra (5 passos)

1. Escreva o checker **antes** da tarefa, sem nome de método (mede comportamento).
2. Monte uma solução de referência e exija **100% de aprovação** (sanidade do fixture).
3. Rode o baseline e exija **reprovação** (o checker discrimina).
4. Trav e o arquivo com `chmod 444`; o agente não o vê nem o altera.
5. Grave `ck:"v3"` + hash do checker em toda medição. Se o checker mudar, a
   série quebra — e está certo.

## Uso

```bash
pip install checker-first

checker-first hash checker.py             # sha256 curto do instrumento
checker-first run checker.py --cwd lane   # veredito ck=v3
checker-first verify --checker checker.py --reference solucao/ --baseline original.py
checker-first api                          # HTTP local :8790
```

API:

```
GET  /health      -> {"ok":true, "ck":"v3"}
GET  /contract    -> as 5 regras
POST /verify      -> {"checker":..., "reference":..., "baseline":...}
```

## O que não é

Não é um runner de pytest bonitinho nem um framework de agentes. É a **prova
de que o veredito é digno de confiança**. O lab da casa usa isto antes de
qualquer conclusão sobre modelo pequeno.

## Licença

MIT. Sem segredo, sem path absoluto, sem dependência de projeto específico.
