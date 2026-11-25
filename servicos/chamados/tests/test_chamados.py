from datetime import datetime

from app.modelos import EventoPendente

CARLA = 4


def abrir(cliente, h, quem="ana", **extra):
    dados = {"titulo": "PC não liga", "descricao": "Nada acontece", "prioridade": "alta", "ativo_id": 1, **extra}
    return cliente.post("/chamados", headers=h[quem], json=dados)


# ---------- regras (iguais ao monólito) ----------

def test_abrir_calcula_sla_e_gera_evento(cliente, h, sessao):
    r = abrir(cliente, h, prioridade="critica")
    assert r.status_code == 201
    c = r.json()
    assert c["solicitante_id"] == 2
    horas = (datetime.fromisoformat(c["prazo_sla"]) - datetime.fromisoformat(c["criado_em"])).total_seconds() / 3600
    assert round(horas) == 4
    with sessao() as db:
        assert db.query(EventoPendente).one().tipo == "ChamadoAberto"


def test_abrir_repassa_o_token_pro_inventario(cliente, h, outros):
    abrir(cliente, h)
    pedido = outros.chamadas[-1]
    assert pedido.url.path == "/ativos/1"
    assert pedido.headers["authorization"] == h["ana"]["Authorization"]


def test_ativo_inexistente(cliente, h):
    assert abrir(cliente, h, ativo_id=999).status_code == 404


def test_atribuir_muda_status(cliente, h, sessao):
    cid = abrir(cliente, h).json()["id"]
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=h["carla"], json={"tecnico_id": CARLA})
    assert r.json()["status"] == "em_atendimento" and r.json()["tecnico_id"] == CARLA
    with sessao() as db:
        assert [e.tipo for e in db.query(EventoPendente)] == ["ChamadoAberto", "ChamadoAtribuido"]


def test_so_tecnico_pode_ser_atribuido(cliente, h):
    cid = abrir(cliente, h).json()["id"]
    assert cliente.patch(f"/chamados/{cid}/atribuir", headers=h["carla"], json={"tecnico_id": 2}).status_code == 422


def test_fluxo_completo(cliente, h):
    cid = abrir(cliente, h).json()["id"]
    cliente.patch(f"/chamados/{cid}/atribuir", headers=h["carla"], json={"tecnico_id": CARLA})
    assert cliente.patch(f"/chamados/{cid}/status", headers=h["carla"], json={"status": "resolvido"}).status_code == 200
    r = cliente.patch(f"/chamados/{cid}/status", headers=h["ana"], json={"status": "fechado"})
    assert r.json()["status"] == "fechado"


def test_transicao_invalida(cliente, h):
    cid = abrir(cliente, h).json()["id"]
    assert cliente.patch(f"/chamados/{cid}/status", headers=h["carla"], json={"status": "fechado"}).status_code == 422


def test_atendimento_sem_tecnico(cliente, h):
    cid = abrir(cliente, h).json()["id"]
    r = cliente.patch(f"/chamados/{cid}/status", headers=h["carla"], json={"status": "em_atendimento"})
    assert r.status_code == 422


def test_comentar(cliente, h):
    cid = abrir(cliente, h).json()["id"]
    r = cliente.post(f"/chamados/{cid}/comentarios", headers=h["carla"], json={"texto": "Verificando a fonte."})
    assert r.status_code == 201 and r.json()["autor_id"] == CARLA
    assert len(cliente.get(f"/chamados/{cid}", headers=h["ana"]).json()["comentarios"]) == 1


def test_painel(cliente, h):
    abrir(cliente, h)
    abrir(cliente, h, prioridade="baixa")
    p = cliente.get("/chamados/painel", headers=h["carla"]).json()
    assert p["total"] == 2 and p["por_status"] == {"aberto": 2}


# ---------- segurança ----------

def test_sem_token_da_401(cliente):
    for metodo, rota in [("get", "/chamados"), ("post", "/chamados"), ("get", "/chamados/painel"), ("get", "/chamados/1")]:
        assert getattr(cliente, metodo)(rota).status_code == 401, rota


def test_solicitante_nao_ve_chamado_dos_outros(cliente, h):
    cid = abrir(cliente, h, quem="ana").json()["id"]
    assert cliente.get(f"/chamados/{cid}", headers=h["bruno"]).status_code == 404
    assert cliente.get("/chamados", headers=h["bruno"]).json() == []


def test_solicitante_nao_atribui_nem_resolve(cliente, h):
    cid = abrir(cliente, h).json()["id"]
    assert cliente.patch(f"/chamados/{cid}/atribuir", headers=h["ana"], json={"tecnico_id": CARLA}).status_code == 403
    assert cliente.patch(f"/chamados/{cid}/status", headers=h["ana"], json={"status": "em_atendimento"}).status_code == 403


def test_nao_abre_em_nome_de_outro(cliente, h):
    assert abrir(cliente, h, solicitante_id=3).status_code == 422


def test_requisicao_grande_demais(cliente, h):
    corpo = '{"titulo": "' + "x" * 70000 + '"}'
    r = cliente.post("/chamados", headers={**h["ana"], "Content-Type": "application/json"}, content=corpo)
    assert r.status_code == 413


# ---------- falhas dos outros serviços ----------

def test_inventario_fora_responde_503(cliente, h, sessao, outros):
    outros.fora.add("inventario")
    r = abrir(cliente, h)
    assert r.status_code == 503 and "Inventário" in r.json()["detail"]
    with sessao() as db:
        assert db.query(EventoPendente).count() == 0  # não salvou nada pela metade


def test_inventario_fora_nao_atrapalha_o_resto(cliente, h, outros):
    abrir(cliente, h, ativo_id=None)
    outros.fora.add("inventario")
    assert cliente.get("/chamados", headers=h["carla"]).status_code == 200
    assert abrir(cliente, h, ativo_id=None).status_code == 201  # sem equipamento nem precisa do inventário


def test_usuarios_fora_na_hora_de_atribuir(cliente, h, outros):
    cid = abrir(cliente, h).json()["id"]
    outros.fora.add("usuarios")
    r = cliente.patch(f"/chamados/{cid}/atribuir", headers=h["carla"], json={"tecnico_id": CARLA})
    assert r.status_code == 503 and "Usuários" in r.json()["detail"]


def test_disjuntor_abre_depois_de_3_falhas(cliente, h, outros):
    outros.fora.add("inventario")
    for _ in range(3):
        abrir(cliente, h)
    antes = len(outros.chamadas)
    assert abrir(cliente, h).status_code == 503
    assert len(outros.chamadas) == antes  # nem tentou chamar a rede
    assert cliente.get("/saude").json()["disjuntores"]["Inventário"] == "aberto"
