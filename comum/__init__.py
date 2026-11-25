"""Biblioteca comum dos microsserviços do HelpDesk.

Contém só o que é *infraestrutura* compartilhada (conferir token, cabeçalhos de
segurança, rastreio, erros e conexão com o banco). Nenhuma regra de negócio mora
aqui: cada serviço continua dono das próprias regras e dos próprios dados.
Cada imagem Docker copia esta pasta no build, então os serviços continuam
sendo implantados de forma independente.
"""
