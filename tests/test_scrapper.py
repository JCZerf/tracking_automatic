from __future__ import annotations

import unittest
from typing import Any

from bot.exceptions import (
    InvalidTrackingCodeError,
    TrackingLimitExceededError,
    TrackingNotFoundError,
    UnsupportedDocumentError,
)
from bot.scrapper import parse_multiple_tracking_results, parse_tracking_codes


def build_tracking_object(code: str, description: str) -> dict[str, Any]:
    return {
        "codObjeto": code,
        "tipoPostal": {"categoria": "SEDEX"},
        "eventos": [
            {
                "descricao": description,
                "dtHrCriado": {
                    "date": "2026-06-21 10:00:00.000000",
                    "timezone": "America/Sao_Paulo",
                },
                "unidade": None,
                "unidadeDestino": None,
            }
        ],
    }


class ParseTrackingCodesTests(unittest.TestCase):
    def test_accepts_single_and_multiple_codes(self) -> None:
        self.assertEqual(
            parse_tracking_codes("TJ 481 246 775 BR"),
            ("TJ481246775BR",),
        )
        self.assertEqual(
            parse_tracking_codes("TJ481246775BR, AP073539958BR"),
            ("TJ481246775BR", "AP073539958BR"),
        )

    def test_rejects_cpf_and_cnpj(self) -> None:
        for document in ("529.982.247-25", "04.252.011/0001-10"):
            with self.subTest(document=document):
                with self.assertRaises(UnsupportedDocumentError):
                    parse_tracking_codes(document)

    def test_rejects_invalid_and_duplicate_codes(self) -> None:
        for value in ("invalid-code", "TJ481246775BR,TJ481246775BR"):
            with self.subTest(value=value):
                with self.assertRaises(InvalidTrackingCodeError):
                    parse_tracking_codes(value)

    def test_rejects_more_than_twenty_codes(self) -> None:
        codes = ",".join(f"AA{index:09d}BR" for index in range(21))

        with self.assertRaises(TrackingLimitExceededError):
            parse_tracking_codes(codes)


class ParseMultipleTrackingResultsTests(unittest.TestCase):
    def test_preserves_requested_order_across_status_groups(self) -> None:
        payload = {
            "transito": [
                {"objeto": build_tracking_object("AP073539958BR", "Em transito")}
            ],
            "entregue": [
                {"objeto": build_tracking_object("TJ481246775BR", "Entregue")}
            ],
        }

        results = parse_multiple_tracking_results(
            payload,
            ("TJ481246775BR", "AP073539958BR"),
        )

        self.assertEqual(
            [result.tracking_code for result in results],
            ["TJ481246775BR", "AP073539958BR"],
        )

    def test_rejects_incomplete_external_response(self) -> None:
        payload = {
            "entregue": [
                {"objeto": build_tracking_object("TJ481246775BR", "Entregue")}
            ]
        }

        with self.assertRaises(TrackingNotFoundError):
            parse_multiple_tracking_results(
                payload,
                ("TJ481246775BR", "AP073539958BR"),
            )


if __name__ == "__main__":
    unittest.main()
