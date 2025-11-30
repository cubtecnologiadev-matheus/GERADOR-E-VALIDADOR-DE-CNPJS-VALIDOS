# 🧾 Gerador e Checker de CNPJs Válidos (Python)

Este projeto contém duas ferramentas em **Python**:

1. `gerador_cnpj.py` → **Gera CNPJs válidos** usando o algoritmo oficial de dígitos verificadores (módulo 11), com vários modos de geração. :contentReference[oaicite:0]{index=0}  
2. `checker_cnpj_biz.py` → **Consulta CNPJs no site cnpj.biz**, em paralelo (multi-thread), e tenta extrair situação cadastral, razão social e CNAE principal. :contentReference[oaicite:1]{index=1}  

---

## 🛠 Tecnologias

- Python 3
- `argparse`, `pathlib`, `random`, `math`, `re`, etc.
- `requests` e `beautifulsoup4` (para o checker)

Instalação dos pacotes extras (recomendado usar venv):

```bash
pip install requests beautifulsoup4
📂 Estrutura do Projeto
text
Copiar código
GERADOR-DE-CNPJS-VALIDOS/
├── gerador_cnpj.py          # Gerador de CNPJs válidos (CLI com subcomandos)
├── checker_cnpj_biz.py      # Checker de CNPJs no cnpj.biz em paralelo
├── out/
│   └── cnpjs_base44622272_00003.txt   # Exemplo de arquivo gerado
└── README.md
1️⃣ gerador_cnpj.py – Gerador de CNPJs
O gerador usa os pesos oficiais de DV do CNPJ (módulo 11) e evita sequências inválidas como 00000000000000. 
gerador_cnpj


Ele funciona com subcomandos:

random → gera CNPJs aleatórios válidos em uma faixa de raiz

seq → gera CNPJs varrendo a base numérica sequencialmente (ótimo pra não repetir)

around → gera CNPJs sem repetir em torno de um CNPJ-base (mesmo “bairro” da raiz)

🔧 Opções comuns (valem para todos os modos)
-o, --output → prefixo da saída (default: out/cnpjs)

Ex.: -o out/cnpjs → gera arquivos out/cnpjs.txt ou out/cnpjs_00001.txt etc.

--mascara → salva no formato 00.000.000/0000-00 (se omitido, grava só os 14 dígitos)

--chunk-size N → divide a saída em arquivos de N linhas cada

Ex.: --chunk-size 1000000

--progress-every N → mostra progresso a cada N linhas

Saída é gerenciada pela classe ChunkWriter, que cria arquivos prefixo_00001.txt, prefixo_00002.txt etc., ou um único .txt se chunk_size=0. 
gerador_cnpj


🔹 Modo random – CNPJs aleatórios válidos
Gera CNPJs válidos em uma faixa de raiz (8 dígitos). 
gerador_cnpj


Parâmetros principais:

-n, --quantidade → obrigatório, quantos CNPJs gerar

--filial-aleatoria → filial entre 0001 e 9999

--filial-fixa N → força a filial para N (ex.: 1 = 0001)

--raiz-min / --raiz-max → faixa da raiz (default: 35.000.000 a 99.999.999)

--bias-newer → puxa mais para raízes próximas do máximo (empurra para “empresas mais novas”)

--seed → seed fixa do random (reprodutível)

🔸 Exemplo 1 – 10.000 CNPJs aleatórios com máscara:

bash
Copiar código
python gerador_cnpj.py random -n 10000 --mascara -o out/cnpjs_random
🔸 Exemplo 2 – 5.000 CNPJs com filial fixa 0001:

bash
Copiar código
python gerador_cnpj.py random -n 5000 --filial-fixa 1 --mascara -o out/cnpjs_fixa0001
🔹 Modo seq – Sequencial (sem repetir)
Varre a base numérica de 12 dígitos (raiz+filial) e calcula os DVs, com opção de sharding e passo. 
gerador_cnpj


Parâmetros principais:

-n, --quantidade → quantidade alvo (se omitir, vai até fim-base12)

--inicio-base12 / --fim-base12 → intervalo da base12 (0..999999999999)

--passo → incremento (default: 1)

--shards-total / --shard-index → permite dividir o espaço em vários “shards”

--nao-pular-seq-invalidas → por padrão, sequências tipo 0000... são puladas; essa flag desabilita isso

🔸 Exemplo – gerar 100.000 CNPJs sequenciais mascarados:

bash
Copiar código
python gerador_cnpj.py seq -n 100000 --mascara -o out/cnpjs_seq --progress-every 10000
🔹 Modo around – Em torno de um CNPJ-base (sem repetir)
Gera CNPJs “perto” de um CNPJ base, com raiz extraída do CNPJ informado (com ou sem máscara). Sempre usa filial 0001. 
gerador_cnpj


Parâmetros:

-n, --quantidade → quantos gerar

--base-cnpj → CNPJ base (ex.: 12.345.678/0001-90 ou 12345678000190)

--spread → faixa de variação da raiz em torno da raiz-base (default: 30.000.000)

--seed → seed para permutação estável

🔸 Exemplo – 500 CNPJs em volta de um CNPJ base:

bash
Copiar código
python gerador_cnpj.py around -n 500 \
  --base-cnpj 12.345.678/0001-90 \
  --mascara \
  -o out/cnpjs_around
2️⃣ checker_cnpj_biz.py – Checker de CNPJs no cnpj.biz
Script que lê uma lista de CNPJs, consulta o site cnpj.biz para cada um e salva os resultados em CSV.
Ele roda com ThreadPoolExecutor para paralelizar as consultas. 
checker_cnpj_biz


🔧 Parâmetros principais
-i, --input → arquivo de entrada com CNPJs (um por linha). Default: cnpjs.txt

-o, --output → CSV de saída. Default: resultados.csv

-t, --threads → número de threads (default: 20)

--proxies → arquivo com proxies (um por linha, formato http://user:pass@host:port)

--delay → atraso (em segundos) entre submissões (ajuda a evitar bloqueios 429/403)

O script:

Normaliza o CNPJ (remove máscara) 
checker_cnpj_biz


Monta a URL https://cnpj.biz/<CNPJ>

Faz a requisição (com retries e rotação de User-Agent)

Usa BeautifulSoup para tentar extrair:

Razão social (h1/h2)

Situação cadastral (campo “Situação Cadastral”)

CNAE principal

Marca como ok=True se conseguiu uma situação plausível

Escreve no CSV com essas colunas:
cnpj, razao_social, situacao, cnae_principal, http_status, ok, url, erro 
checker_cnpj_biz


▶️ Como usar o checker
1. Preparar o arquivo de entrada
Crie um arquivo cnpjs.txt com um CNPJ por linha:

text
Copiar código
12.345.678/0001-90
12345678000190
11.222.333/0001-01
...
Máscara ou sem máscara, o script normaliza tudo.

2. Rodar o checker básico
bash
Copiar código
python checker_cnpj_biz.py -i cnpjs.txt -o resultados.csv
Enquanto roda, ele vai printando algo como:

text
Copiar código
[200] 12345678000190  ->  ATIVA
[200] 11222333000101  ->  BAIXADA
...
No final:

text
Copiar código
✅ Finalizado! CSV salvo em: <caminho completo do resultados.csv>
3. Usar com mais threads, delay e proxies
bash
Copiar código
python checker_cnpj_biz.py \
  -i cnpjs.txt \
  -o resultados.csv \
  -t 30 \
  --delay 0.5 \
  --proxies proxies.txt
Arquivo proxies.txt (um por linha):

text
Copiar código
http://user:senha@host1:porta
http://host2:porta
...
⚠ Aviso de uso
O gerador de CNPJs cria números válidos matematicamente, mas isso não significa que existam na Receita Federal.

O checker acessa um site de terceiros (cnpj.biz). Use com moderação, respeitando:

Termos de uso do site

Limites de requisição (por isso existem --delay, --threads e --proxies)

Este projeto é voltado para estudos, testes, simulações e QA.
Uso em produção, automação em massa ou fins comerciais é por sua conta e risco.

👨‍💻 Autor
Matheus – Cub Tecnologia Dev
Ferramentas em Python, PHP e Node.js focadas em automação, validação e geração de dados.
📧 cubtecnologia.dev@gmail.com
