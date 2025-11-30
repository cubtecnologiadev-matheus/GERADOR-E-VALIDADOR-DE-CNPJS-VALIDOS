#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import csv
import time
import html
import random
import argparse
import concurrent.futures as cf
from pathlib import Path

import requests
from bs4 import BeautifulSoup

UA_LIST = [
    # alguns UAs modernos pra variar as requisições
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

TIMEOUT = 20
RETRY = 3

def normalizar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj)

def montar_url(cnpj_num: str) -> str:
    return f"https://cnpj.biz/{cnpj_num}"

def fetch(session: requests.Session, url: str) -> requests.Response | None:
    for tent in range(RETRY):
        try:
            hdrs = {
                "User-Agent": random.choice(UA_LIST),
                "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
            }
            resp = session.get(url, headers=hdrs, timeout=TIMEOUT)
            # aceitamos 200; em 403/429 vamos esperar um pouco e tentar de novo
            if resp.status_code == 200:
                return resp
            elif resp.status_code in (403, 429):
                time.sleep(1.5 + tent)
            else:
                return resp
        except requests.RequestException:
            time.sleep(1.0 + tent * 0.5)
    return None

def parse_pagina(html_text: str) -> dict:
    """
    Tenta extrair:
    - razao_social (título/heading)
    - situacao (valor do campo 'Situação Cadastral')
    - cnae_principal (opcional)
    """
    soup = BeautifulSoup(html_text, "html.parser")

    # Razão Social: geralmente aparece no <title> e/ou em heading na página
    titulo = soup.find(["h1", "h2"])
    razao = titulo.get_text(strip=True) if titulo else None

    # Busca por linha 'Situação Cadastral'
    situacao = None
    # 1) Tabela com th/td
    for th in soup.find_all("th"):
        if "Situação Cadastral" in th.get_text(" ", strip=True):
            td = th.find_next("td")
            if td:
                situacao = td.get_text(" ", strip=True)
                break
    # 2) fallback: regex no HTML bruto
    if not situacao:
        m = re.search(r"Situa[cç][aã]o\s+Cadastral\s*:\s*</?\w*>\s*([A-ZÇÃÂÉÍÓÚ ]+)", html_text, re.IGNORECASE)
        if m:
            situacao = m.group(1).strip()

    # CNAE principal (se existir)
    cnae = None
    for th in soup.find_all("th"):
        if "CNAE" in th.get_text(" ", strip=True):
            td = th.find_next("td")
            if td:
                cnae = td.get_text(" ", strip=True)
                break

    return {
        "razao_social": razao,
        "situacao": situacao,
        "cnae_principal": cnae,
    }

def worker(cnpj: str, proxies: list[str] | None = None) -> dict:
    cnpj_num = normalizar_cnpj(cnpj)
    url = montar_url(cnpj_num)
    proxy = None
    if proxies:
        proxy = random.choice(proxies)
    prx = {"http": proxy, "https": proxy} if proxy else None

    with requests.Session() as s:
        if prx:
            s.proxies.update(prx)
        resp = fetch(s, url)
        result = {
            "cnpj": cnpj_num,
            "url": url,
            "http_status": getattr(resp, "status_code", None),
            "razao_social": None,
            "situacao": None,
            "cnae_principal": None,
            "ok": False,
            "erro": None,
        }
        if resp is None:
            result["erro"] = "Sem resposta após retries"
            return result
        if resp.status_code != 200:
            result["erro"] = f"HTTP {resp.status_code}"
            return result

        dados = parse_pagina(resp.text)
        result.update(dados)
        # Considera OK se conseguiu extrair um 'Situação' plausível
        if dados.get("situacao"):
            result["ok"] = True
        return result

def main():
    ap = argparse.ArgumentParser(description="Checker de CNPJ no cnpj.biz (multi-threads).")
    ap.add_argument("-i", "--input", default="cnpjs.txt", help="Arquivo com CNPJs (um por linha)")
    ap.add_argument("-o", "--output", default="resultados.csv", help="CSV de saída")
    ap.add_argument("-t", "--threads", type=int, default=20, help="Número de threads (default: 20)")
    ap.add_argument("--proxies", help="Arquivo com proxies (http://user:pass@host:port), um por linha")
    ap.add_argument("--delay", type=float, default=0.0, help="Atraso (segundos) entre envios (para aliviar bloqueios)")
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        raise SystemExit(f"Arquivo de entrada não encontrado: {inp}")

    proxies = None
    if args.proxies:
        pf = Path(args.proxies)
        if pf.exists():
            proxies = [ln.strip() for ln in pf.read_text(encoding="utf-8").splitlines() if ln.strip()]

    cnpjs = [ln.strip() for ln in inp.read_text(encoding="utf-8").splitlines() if ln.strip()]
    outp = Path(args.output)

    campos = ["cnpj", "razao_social", "situacao", "cnae_principal", "http_status", "ok", "url", "erro"]
    with outp.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()

        with cf.ThreadPoolExecutor(max_workers=max(1, args.threads)) as ex:
            futs = []
            for idx, c in enumerate(cnpjs):
                if args.delay and idx:
                    time.sleep(args.delay)
                futs.append(ex.submit(worker, c, proxies))
            for fu in cf.as_completed(futs):
                r = fu.result()
                w.writerow(r)
                situ = r.get("situacao") or "?"
                print(f"[{r['http_status']}] {r['cnpj']}  ->  {situ}")

    print(f"✅ Finalizado! CSV salvo em: {outp.resolve()}")

if __name__ == "__main__":
    main()
