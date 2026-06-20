url: https://rastreamento.correios.com.br/app/index.php

Código de teste: TJ 481 246 775 BR

## API

```powershell
.venv\Scripts\uvicorn.exe main:app --reload
```

Consulta:

```text
GET http://127.0.0.1:8000/tracking?code=TJ%20481%20246%20775%20BR
```

Documentação interativa: `http://127.0.0.1:8000/docs`

## Docker

```powershell
docker compose up --build -d
docker compose logs -f
```

O Compose limita o serviço a 1 CPU e 512 MB de RAM. Nesse perfil, as consultas
são processadas uma por vez para evitar concorrência no PaddleOCR.

Para encerrar:

```powershell
docker compose down
```
