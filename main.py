"""Ponto de entrada ASGI da aplicacao."""

from api.app import create_app


app = create_app()
