# checker-first

**Checker escrito antes, travado e provado nos dois sentidos.**

Padrão extraído do laboratório A/B da casa, onde 9 horas e 537 ciclos foram
perdidos porque um checker pedia um mapa impossível — e todo mundo reprovava.
A correção não foi um modelo melhor: foi **validar o instrumento antes de medir**.

## O caso que este pacote existe para pegar

No laboratório, o checker de pathfinding exigia que o inimigo contornasse uma
parede interna que, no fixture, **tapava o mapa inteiro**. A passagem não
existia. Resultado: 537 ciclos, 9 horas, e todo mundo reprovando. Nenhum modelo
era o culpado: o **instrumento** era impossível.

A primeira versão deste pacote provava que a referência passa e o baseline
falha. Com um checker impossível, o baseline falhava (ok) e a referência
**também** — e a prova devolvia `valido: false` sem dizer **qual** dos dois
defeitos era. O time via "o checker não está bom" e seguia medindo.

A v0.1.1 distingue os três estados:

| `verdict` | o que aconteceu | o que fazer |
|---|---|---|
| `ok` | a referência passa e o baseline falha | pode medir |
| `fixture_invalido` | **a referência também reprovou**: o cenário é impossível | **PARE** a série; corrija o cenário ou a referência |
| `nao_discrimina` | a referência passou e o baseline também | o checker não separa nada; aumente a exigência |

## Regra (5 passos)

1. Escreva o checker **antes** da tarefa, sem nome de método (mede comportamento).
2. Monte uma solução de referência e exija **100% de aprovação** (sanidade do fixture).
3. Rode o baseline e exija **reprovação** (o checker discrimina).
4. Trave o arquivo com `chmod 444`; o agente não o vê nem o altera.
5. Grave `ck:"v3"` + hash do checker em toda medição. Se o checker mudar, a
   série quebra — e está certo.

## Uso

```bash
pip install checker-first

checker-first doctor --checker checker.py --reference solucao.py --baseline original.py
checker-first hash checker.py             # sha256 curto do instrumento
checker-first run checker.py --cwd lane   # veredito ck=v3
checker-first verify --checker checker.py --reference solucao.py --baseline original.py
checker-first api                          # HTTP local :8790
```

O `doctor` sai com **código 1** quando o instrumento não serve, então um
script de série podeeze sem ler o JSON:

```bash
checker-first doctor --checker c.py --reference s.py --baseline b.py || exit 1
```

API:

```
GET  /health      -> {"ok":true, "ck":"v3", "version":"0.1.1"}
GET  /contract    -> as 5 regras e os 3 verdicts
POST /verify      -> {"checker":..., "reference":..., "baseline":...}
POST /verify      -> com "mode":"doctor" devolve o diagnostico do instrumento
```

## O que não é

Não é um runner de pytest bonitinho nem um framework de agentes. É a **prova
de que o veredito é digno de confiança**. O lab da casa usa isto antes de
medir qualquer modelo.

## Agnóstico

O pacote não sabe nada do laboratório, do opencode nem da casa: não há path
absoluto, nome de projeto nem segredo. O único contexto é o **princípio** e o
**caso medido** que o motivou.

## Anti-redescoberta

Se você já perdeu tempo com um instrumento inválido, a ordem é: `doctor`
primeiro, série depois. Se o `doctor` disser `fixture_invalido`, o problema
**não é o modelo** — e nenhum número de token gasto em medir vai mudar isso.

## Licença

MIT. Ver [LICENSE](LICENSE).
