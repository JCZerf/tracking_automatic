# Tracking Automatic

Aplicação monolítica em FastAPI para consultar o histórico de objetos dos Correios.
A API baixa a página de rastreamento, resolve o CAPTCHA com OCR e retorna os eventos em formato estruturado.

## Visão geral

A aplicação está organizada em três blocos principais:

- `api/`: camada HTTP e rotas da API
- `bot/`: lógica de scraping e modelos de resposta
- `solver/`: reconhecimento de CAPTCHA com PaddleOCR

O ponto de entrada da aplicação é [main.py](main.py), que cria a instância do FastAPI.

## Fluxo da aplicação

1. A API recebe um código de rastreamento.
2. O scraper acessa o site dos Correios.
3. O OCR resolve o CAPTCHA.
4. A resposta é estruturada e retornada em JSON.

## Requisitos

- Python 3.12+
- Dependências listadas em [requirements.txt](requirements.txt)
- Docker e Docker Compose (opcional, para execução local em ambiente semelhante ao deploy)

## Configuração local

Crie e ative um ambiente virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

Execute a aplicação:

```powershell
uvicorn main:app --reload
```

A aplicação fica disponível em:

- `http://127.0.0.1:8000/` → redireciona para a documentação Swagger
- `http://127.0.0.1:8000/docs` → documentação interativa

## Exemplo de requisição

```http
GET /tracking?code=TJ 481 246 775 BR
```

Exemplo com URL codificada:

```text
GET http://127.0.0.1:8000/tracking?code=TJ%20481%20246%20775%20BR
```

## Documentação da API

A documentação automática do Swagger está disponível em:

```text
http://127.0.0.1:8000/docs
```

## Execução com Docker

Subir o serviço:

```powershell
docker compose up --build -d
```

Ver logs:

```powershell
docker compose logs -f
```

Parar o serviço:

```powershell
docker compose down
```

O arquivo [compose.yaml](compose.yaml) define um perfil com limite de 1 CPU e 512 MB de RAM para reduzir risco de concorrência durante o reconhecimento do CAPTCHA.

## Deploy

A aplicação já inclui um [Dockerfile](Dockerfile) preparado para deploy em plataformas que executam containers, como Render.

Recomendações para deploy:

- usar a porta definida pela variável `PORT` no ambiente
- manter o serviço com pelo menos 1 CPU e 1 GB de RAM para melhor estabilidade com OCR
- preferir containers em vez de execução direta em ambientes muito limitados

## Observações importantes

- A lógica de OCR está centralizada em [solver/paddle_ocr.py](solver/paddle_ocr.py).
- O scraping dos Correios está em [bot/scrapper.py](bot/scrapper.py).
- As rotas HTTP estão em [api/routes/tracking.py](api/routes/tracking.py).
- A inicialização da aplicação e a configuração do FastAPI estão em [api/app.py](api/app.py).
