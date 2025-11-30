#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from pathlib import Path
import random
import sys
import math
import re

# Pesos oficiais do DV do CNPJ (módulo 11)
PESOS_DV1 = [5,4,3,2,9,8,7,6,5,4,3,2]
PESOS_DV2 = [6,5,4,3,2,9,8,7,6,5,4,3,2]

def dv_mod11(numeros, pesos):
    s = sum(d * p for d, p in zip(numeros, pesos))
    r = s % 11
    return 0 if r < 2 else 11 - r

def calc_dvs(base12_digits):
    d1 = dv_mod11(base12_digits, PESOS_DV1)
    d2 = dv_mod11(base12_digits + [d1], PESOS_DV2)
    return d1, d2

def mascarar(cnpj):
    return f"{cnpj[0:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"

def is_sequencia_invalida(cnpj14str):
    # evita 00000000000000, 1111..., etc.
    return len(set(cnpj14str)) == 1

def parse_cnpj_like(s: str) -> tuple[int,int]:
    """
    Extrai raiz (8 dígitos) e filial (4 dígitos) de uma string que contenha CNPJ (com ou sem máscara).
    Se não houver 14 dígitos, tenta extrair melhor esforço.
    """
    nums = re.sub(r"\D", "", s or "")
    if len(nums) < 12:
        raise ValueError("Entrada não tem dígitos suficientes para raiz+filial (mín. 12).")
    raiz = int(nums[0:8])
    filial = int(nums[8:12])
    return raiz, filial

# ---------- Escrita em chunks ----------
class ChunkWriter:
    """Grava em chunks: base_prefix_00001.txt, _00002.txt... ou único .txt se chunk_size=0"""
    def __init__(self, base_prefix: Path, chunk_size: int, progress_every: int):
        self.base_prefix = base_prefix
        self.chunk_size = max(0, chunk_size)
        self.progress_every = max(0, progress_every)
        self._count_total = 0
        self._count_chunk = 0
        self._chunk_idx = 0
        self._fh = None
        self.base_prefix.parent.mkdir(parents=True, exist_ok=True)

    def _open_next(self):
        if self._fh:
            self._fh.close()
        self._chunk_idx += 1
        if self.chunk_size > 0:
            path = self.base_prefix.parent / f"{self.base_prefix.name}_{self._chunk_idx:05d}.txt"
        else:
            path = self.base_prefix.with_suffix(".txt")
        self._fh = path.open("w", encoding="utf-8")
        self._count_chunk = 0
        if self.chunk_size > 0:
            print(f"[chunk] escrevendo: {path}")

    def write_line(self, line: str):
        if self._fh is None:
            self._open_next()
        if self.chunk_size > 0 and self._count_chunk >= self.chunk_size:
            self._open_next()
        self._fh.write(line)
        self._fh.write("\n")
        self._count_chunk += 1
        self._count_total += 1
        if self.progress_every and (self._count_total % self.progress_every == 0):
            print(f"… {self._count_total:,} gerados", file=sys.stderr)

    def close(self):
        if self._fh:
            self._fh.close()
            self._fh = None

# ---------- Geradores de CNPJ ----------
def montar_cnpj(raiz8: int, filial4: int, com_mascara: bool) -> str | None:
    base12 = [int(x) for x in f"{raiz8:08d}{filial4:04d}"]
    d1, d2 = calc_dvs(base12)
    cnpj14 = "".join(str(x) for x in (base12 + [d1, d2]))
    if is_sequencia_invalida(cnpj14):
        return None
    return mascarar(cnpj14) if com_mascara else cnpj14

def gerar_random_uma_linha(filial_aleatoria, filial_fixa, com_mascara,
                           raiz_min, raiz_max, bias_newer) -> str:
    # raiz (8 dígitos)
    if bias_newer:
        val = int(random.triangular(raiz_min, raiz_max + 1, raiz_max))
    else:
        val = random.randint(raiz_min, raiz_max)
    # filial
    if filial_aleatoria:
        filial = random.randint(1, 9999)
    else:
        filial = 1 if filial_fixa is None else int(filial_fixa)
    return montar_cnpj(val, filial, com_mascara)

# Permutação aritmética: i -> (a*i + b) mod N (com a coprimo a N)
def permute_index(i: int, N: int, a: int, b: int) -> int:
    return (a * i + b) % N

def coprime_to(N: int) -> int:
    # pega um 'a' aleatório coprimo de N
    while True:
        a = random.randrange(2, N-1)
        if math.gcd(a, N) == 1:
            return a

# ---------- CLI ----------
def main():
    # opções comuns (funcionam antes OU depois do subcomando)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-o", "--output", default="out/cnpjs",  # prefixo base, sem extensão
                        help="Prefixo da saída. Ex.: out/cnpjs -> out/cnpjs.txt (sem chunk) "
                             "ou out/cnpjs_00001.txt (com chunk).")
    common.add_argument("--mascara", action="store_true",
                        help="Salvar com máscara 00.000.000/0000-00")
    common.add_argument("--chunk-size", type=int, default=0,
                        help="Se >0, divide em arquivos de N linhas (ex.: 1000000).")
    common.add_argument("--progress-every", type=int, default=0,
                        help="Progresso a cada N linhas (0 = silencioso).")

    ap = argparse.ArgumentParser(
        description="Gerador de CNPJ (módulo 11) — random/seq/around com sharding + chunking."
    )
    modos = ap.add_subparsers(dest="modo", required=True)

    # --- Modo aleatório (faixa de raiz) ---
    r = modos.add_parser("random", parents=[common], help="Gerar CNPJs aleatórios válidos (faixa de raiz)")
    r.add_argument("-n", "--quantidade", type=int, required=True, help="Quantidade para gerar")
    r.add_argument("--filial-aleatoria", action="store_true", help="Filial aleatória (0001–9999)")
    r.add_argument("--filial-fixa", type=int, help="Filial fixa (ex.: 1 = 0001)")
    r.add_argument("--seed", type=int, help="Seed do PRNG")
    r.add_argument("--raiz-min", type=int, default=35_000_000, help="Mínimo da raiz (8 dígitos)")
    r.add_argument("--raiz-max", type=int, default=99_999_999, help="Máximo da raiz (8 dígitos)")
    r.add_argument("--bias-newer", action="store_true",
                   help="Favorece raízes próximas ao máximo (triangular com moda=raiz_max)")

    # --- Modo sequencial (zero duplicados) ---
    s = modos.add_parser("seq", parents=[common], help="Gerar CNPJs varrendo base12 sequencialmente")
    s.add_argument("-n", "--quantidade", type=int, help="Quantidade alvo (se omitido, vai até 'fim')")
    s.add_argument("--inicio-base12", type=int, help="Início da base12 (0..999999999999) — inclusive")
    s.add_argument("--fim-base12", type=int, help="Fim da base12 (0..999999999999) — inclusive")
    s.add_argument("--passo", type=int, default=1, help="Passo entre bases (default: 1)")
    s.add_argument("--shards-total", type=int, default=1, help="Total de shards (default: 1)")
    s.add_argument("--shard-index", type=int, default=0, help="Índice deste shard (0..shards_total-1)")
    s.add_argument("--nao-pular-seq-invalidas", action="store_true",
                   help="Não pular sequências tipo 000000... (por padrão são puladas)")

    # --- Modo around (NOVO): aleatório SEM repetir, em torno de um CNPJ-base, com filial 0001 ---
    a = modos.add_parser("around", parents=[common],
                         help="Aleatório sem repetir ao redor de um CNPJ-base (filial 0001 fixa).")
    a.add_argument("-n", "--quantidade", type=int, required=True,
                   help="Quantidade a gerar na faixa ao redor.")
    a.add_argument("--base-cnpj", type=str, required=True,
                   help="CNPJ base (com ou sem máscara). A raiz (8 dígitos) será extraída.")
    a.add_argument("--spread", type=int, default=30_000_000,
                   help="Quanto expandir para baixo/acima da raiz-base (em unidades de raiz). "
                        "Faixa = [raiz - spread, raiz + spread], truncada a 0..99_999_999.")
    a.add_argument("--seed", type=int, help="Seed para permutação (estável).")

    args = ap.parse_args()

    base_prefix = Path(args.output)
    writer = ChunkWriter(base_prefix=base_prefix,
                         chunk_size=getattr(args, "chunk_size", 0),
                         progress_every=getattr(args, "progress_every", 0))

    try:
        if args.modo == "random":
            if args.seed is not None:
                random.seed(args.seed)
            if args.raiz_min < 0 or args.raiz_max > 99_999_999 or args.raiz_min > args.raiz_max:
                raise SystemExit("--raiz-min/--raiz-max inválidos (0..99999999 e min <= max)")
            alvo = args.quantidade
            gerados = 0
            while gerados < alvo:
                line = gerar_random_uma_linha(
                    filial_aleatoria=args.filial_aleatoria,
                    filial_fixa=args.filial_fixa,
                    com_mascara=args.mascara,
                    raiz_min=args.raiz_min,
                    raiz_max=args.raiz_max,
                    bias_newer=args.bias_newer,
                )
                if line is None:
                    continue
                writer.write_line(line)
                gerados += 1

        elif args.modo == "seq":
            inicio = 0 if args.inicio_base12 is None else args.inicio_base12
            fim = 999_999_999_999 if args.fim_base12 is None else args.fim_base12
            if not (0 <= args.shard_index < args.shards_total):
                raise SystemExit(f"Shard inválido: index={args.shard_index}, total={args.shards_total}")

            offset = (args.shard_index - (inicio % args.shards_total)) % args.shards_total
            i = inicio + offset

            alvo = args.quantidade
            emitidos = 0
            while i <= fim and (alvo is None or emitidos < alvo):
                base12 = f"{i:012d}"
                base12_digits = [int(ch) for ch in base12]
                d1, d2 = calc_dvs(base12_digits)
                cnpj14 = "".join(str(x) for x in (base12_digits + [d1, d2]))

                if args.nao_pular_seq_invalidas or not is_sequencia_invalida(cnpj14):
                    writer.write_line(mascarar(cnpj14) if args.mascara else cnpj14)
                    emitidos += 1

                i += args.passo * args.shards_total

        else:  # around
            if args.seed is not None:
                random.seed(args.seed)
            raiz_base, _filial = parse_cnpj_like(args.base_cnpj)
            # faixa de raízes
            lo = max(0, raiz_base - args.spread)
            hi = min(99_999_999, raiz_base + args.spread)
            N = hi - lo + 1
            if args.quantidade > N:
                raise SystemExit(f"Quantidade ({args.quantidade}) maior que o tamanho da faixa ({N}). "
                                 f"Ajuste --spread ou reduza -n.")
            # permutação aritmética sobre 0..N-1
            a_coef = coprime_to(N)
            b_coef = random.randrange(0, N)
            # filial fixa 0001
            filial4 = 1
            emitidos = 0
            i = 0
            while emitidos < args.quantidade:
                j = permute_index(i, N, a_coef, b_coef)
                raiz = lo + j
                line = montar_cnpj(raiz, filial4, args.mascara)
                if line is None:
                    # sequência inválida é raríssima aqui; apenas pula
                    i += 1
                    continue
                writer.write_line(line)
                emitidos += 1
                i += 1

    finally:
        writer.close()

if __name__ == "__main__":
    main()
