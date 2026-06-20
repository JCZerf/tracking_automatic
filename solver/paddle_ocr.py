"""Reconhecimento de CAPTCHAs usando exclusivamente PaddleOCR."""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from paddleocr import PaddleOCR


DEFAULT_IMAGES_DIR = Path(__file__).resolve().parent.parent / "artefatos" / "img_captcha"
SUPPORTED_IMAGE_EXTENSIONS = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Resultado do reconhecimento de uma imagem."""

    image_path: Path
    text: str
    confidence: float
    elapsed_seconds: float


class PaddleCaptchaOcr:
    """Mantem uma instancia do PaddleOCR pronta para reconhecer CAPTCHAs."""

    def __init__(self, language: str = "pt") -> None:
        self._ocr = PaddleOCR(
            lang=language,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )

    def recognize(self, image_path: Path | str) -> OcrResult:
        """Reconhece o texto de uma imagem e devolve seus dados de execucao."""
        path = Path(image_path).expanduser().resolve()
        self._validate_image(path)

        started_at = time.perf_counter()
        pages = self._ocr.predict(str(path))
        elapsed_seconds = time.perf_counter() - started_at
        texts, scores = self._extract_recognitions(pages)

        return OcrResult(
            image_path=path,
            text="".join(texts).strip(),
            confidence=sum(scores) / len(scores) if scores else 0.0,
            elapsed_seconds=elapsed_seconds,
        )

    def recognize_many(self, image_paths: Iterable[Path | str]) -> list[OcrResult]:
        """Reconhece varias imagens reutilizando o mesmo modelo carregado."""
        return [self.recognize(image_path) for image_path in image_paths]

    @staticmethod
    def _validate_image(image_path: Path) -> None:
        if not image_path.is_file():
            raise FileNotFoundError(f"Imagem nao encontrada: {image_path}")
        if image_path.suffix.lower() not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"Formato de imagem nao suportado: {image_path.suffix}")

    @staticmethod
    def _extract_recognitions(pages: Iterable[Any] | None) -> tuple[list[str], list[float]]:
        texts: list[str] = []
        scores: list[float] = []

        for page in pages or []:
            if not hasattr(page, "get"):
                raise TypeError("Formato de resposta inesperado do PaddleOCR 3.x")

            texts.extend(str(text) for text in (page.get("rec_texts") or []) if text)
            scores.extend(float(score) for score in (page.get("rec_scores") or []))

        return texts, scores


def find_images(source: Path) -> list[Path]:
    """Retorna uma imagem isolada ou as imagens de um diretorio."""
    source = source.expanduser().resolve()
    if source.is_file():
        return [source]
    if not source.is_dir():
        raise FileNotFoundError(f"Caminho nao encontrado: {source}")

    return sorted(
        path
        for path in source.iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_IMAGE_EXTENSIONS
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Reconhece CAPTCHAs com PaddleOCR 3.x.")
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=DEFAULT_IMAGES_DIR,
        help="Imagem ou diretorio de imagens.",
    )
    parser.add_argument("--language", default="pt", help="Idioma do modelo (padrao: pt).")
    return parser


def print_results(results: Sequence[OcrResult]) -> None:
    for result in results:
        text = result.text or "[sem resultado]"
        print(
            f"{result.image_path.name}: {text} "
            f"(confianca: {result.confidence:.2%}, tempo: {result.elapsed_seconds:.2f}s)"
        )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        images = find_images(args.source)
        if not images:
            print(f"Nenhuma imagem encontrada em: {args.source}")
            return 1

        recognizer = PaddleCaptchaOcr(language=args.language)
        print_results(recognizer.recognize_many(images))
        return 0
    except Exception as error:
        print(f"Erro ao executar o PaddleOCR: {type(error).__name__}: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
