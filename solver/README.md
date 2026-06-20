# Validação de OCR para CAPTCHA

Script para comparar 3 bibliotecas de OCR e determinar qual é mais precisa para resolver seus CAPTCHAs.

## Bibliotecas testadas:

- **EasyOCR**: Deep learning, alta precisão, mais pesada
- **PaddleOCR**: Rápida, bom equilíbrio, otimizada
- **Tesseract**: Clássica, leve, requer pré-processamento

## Instalação rápida

```bash
pip install easyocr paddleocr opencv-python numpy
python validate_ocr.py
```

## Detalhes de instalação

### 1. Dependências principais:

```bash
pip install -r requirements_ocr.txt
```

### 2. (Opcional) Tesseract:

Se quiser testar também Tesseract:

1. Instale o pacote:

```bash
pip install pytesseract
```

2. Baixe o executável:
   - Manual: https://github.com/UB-Mannheim/tesseract/wiki (instale em `C:\Program Files\Tesseract-OCR`)
   - Ou tente: `choco install tesseract` (requer privilégios admin)

## Uso

```bash
python validate_ocr.py
```

## O script faz:

1. ✓ Testa as 3 bibliotecas em todas as imagens
2. ✓ Mostra tempo de execução
3. ✓ Exibe resultados de cada OCR
4. ✓ Gera relatório comparativo

## Resultado esperado:

```
RELATÓRIO FINAL
===============
⏱️  TEMPO MÉDIO DE EXECUÇÃO:
   EasyOCR        : 2.45s
   PaddleOCR      : 0.85s
   Tesseract      : 0.32s

📊 RESULTADOS OBTIDOS:
   [comparação dos textos extraídos]
```

## Próximos passos:

Após rodar o script, escolha a biblioteca com melhor precisão e implemente em `solver/captcha_solver.py`
