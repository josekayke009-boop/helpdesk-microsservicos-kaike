"""Roda uma vez, no primeiro `docker compose up`, dentro do contêiner `segredos`.

Gera o segredo do JWT e a senha de cada banco MySQL num volume Docker.
Assim nenhuma senha fica escrita no código nem no docker-compose.yml, e o
professor não precisa criar .env nenhum pra rodar.
Se o arquivo já existe, não mexe (senão os bancos já criados não abririam mais).
"""
import os
import secrets
from pathlib import Path

PASTA = Path("/segredos")
NOMES = ["jwt_segredo", "bd_usuarios", "bd_inventario", "bd_chamados", "bd_notificacoes"]

for nome in NOMES:
    arquivo = PASTA / nome
    if arquivo.exists():
        print(f"{nome}: já existe")
        continue
    arquivo.write_text(secrets.token_urlsafe(48))
    # leitura pra todos os contêineres que montam o volume (os serviços rodam com outro usuário)
    os.chmod(arquivo, 0o444)
    print(f"{nome}: criado")
