"""Servidor HTTP e API REST da interface de comando Porta GEAR.

Totalmente desacoplado e protegido com autenticação e validação de sessão contra bypass.
Funciona exclusivamente como um adaptador HTTP que valida as credenciais de acesso
e despacha cada requisição para a camada unificada de serviços (ServicosPorta).
"""

from __future__ import annotations

import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import mimetypes
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from urllib.parse import urlparse, parse_qs

# Garante acesso aos módulos do projeto
PASTA_WEB = Path(__file__).resolve().parent
PASTA_PROJETO = PASTA_WEB.parent
if str(PASTA_PROJETO) not in sys.path:
    sys.path.insert(0, str(PASTA_PROJETO))

from src.modulo_central.gestor_modo import ErroModoBloqueado
from src.modulo_central.servicos_porta import ServicosPorta
from src.modulo_database.database import ErroDatabase
from src.modulo_database.setup_database import CAMINHO_DATABASE_PADRAO


class RequisicaoHandler(BaseHTTPRequestHandler):
    """Adaptador HTTP REST seguro para os serviços da Porta GEAR."""

    servicos: ServicosPorta

    def address_string(self):
        # Retorna o IP direto evitando timeout de DNS reverso (getfqdn)
        return self.client_address[0]

    def log_message(self, format, *args):
        # Log limpo e legível no console
        sys.stdout.write(f"[{time.strftime('%H:%M:%S')}] {self.address_string()} - {format % args}\n")

    def _responder_json(self, status_code: int, dados: dict | list):
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()
        self.wfile.write(corpo)

    def _responder_erro(self, status_code: int, mensagem: str):
        self._responder_json(status_code, {"sucesso": False, "erro": mensagem})

    def _ler_json_body(self) -> dict:
        tamanho = int(self.headers.get("Content-Length", 0))
        if tamanho <= 0:
            return {}
        dados = self.rfile.read(tamanho)
        return json.loads(dados.decode("utf-8"))

    def _obter_token_requisicao(self) -> str | None:
        """Extrai o token dos cabeçalhos Authorization ou X-Auth-Token."""
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            return auth_header[7:].strip()
        x_token = self.headers.get("X-Auth-Token", "")
        if x_token:
            return x_token.strip()
        return None

    def _verificar_autenticacao(self, rota: str) -> bool:
        """Garante que a requisição possua credencial válida para proteção anti-bypass."""
        # Rotas públicas que não exigem token
        if rota in ("/", "/index.html", "/api/auth/login") or rota.startswith("/static/"):
            return True

        token = self._obter_token_requisicao()
        if not self.servicos.validar_token(token):
            self._responder_json(401, {
                "sucesso": False,
                "erro": "Acesso não autorizado. Digite a senha do administrador.",
                "requer_login": True,
            })
            return False
        return True

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Auth-Token")
        self.end_headers()

    # -------------------------------------------------------------------------
    # ROTAS GET
    # -------------------------------------------------------------------------
    def do_GET(self):
        url = urlparse(self.path)
        rota = url.path.rstrip("/")
        if not rota:
            rota = "/"

        # Rota da página principal
        if rota in ("/", "/index.html"):
            return self._servir_arquivo(PASTA_WEB / "templates" / "index.html")

        # Rota de arquivos estáticos (CSS, JS, imagens)
        if rota.startswith("/static/"):
            caminho_rel = rota[len("/static/"):]
            arquivo = (PASTA_WEB / "static" / caminho_rel).resolve()
            if str(arquivo).startswith(str((PASTA_WEB / "static").resolve())):
                return self._servir_arquivo(arquivo)
            return self._responder_erro(403, "Acesso proibido.")

        # Validação obrigatória de segurança
        if not self._verificar_autenticacao(rota):
            return

        # API: Verificação de token de autenticação
        if rota == "/api/auth/verificar":
            return self._responder_json(200, {
                "sucesso": True,
                "autenticado": True,
                "mensagem": "Sessão válida.",
            })

        # API: Status consolidado do sistema
        if rota == "/api/status":
            return self._responder_json(200, self.servicos.obter_status())

        # API: Listagem de usuários
        if rota == "/api/usuarios":
            params = parse_qs(url.query)
            busca = params.get("busca", [None])[0]
            return self._responder_json(200, self.servicos.listar_usuarios(busca=busca))

        # API: Detalhes de um usuário
        if rota.startswith("/api/usuarios/"):
            id_usuario = rota.split("/")[-1]
            try:
                return self._responder_json(200, self.servicos.obter_usuario(id_usuario))
            except ErroDatabase as e:
                return self._responder_erro(404, str(e))

        # API: Registros de auditoria de acessos
        if rota == "/api/registros":
            params = parse_qs(url.query)
            limite = int(params.get("limite", [30])[0])
            registros = self.servicos.obter_registros(limite=limite)
            return self._responder_json(200, {"sucesso": True, "registros": registros})

        self._responder_erro(404, "Endpoint não encontrado.")

    # -------------------------------------------------------------------------
    # ROTAS POST
    # -------------------------------------------------------------------------
    def do_POST(self):
        url = urlparse(self.path)
        rota = url.path.rstrip("/")

        try:
            body = self._ler_json_body()
        except Exception as e:
            return self._responder_erro(400, f"JSON inválido: {e}")

        # API: Login de Administrador (Pública)
        if rota == "/api/auth/login":
            senha = body.get("senha", "")
            try:
                resultado = self.servicos.autenticar_admin(senha)
                return self._responder_json(200, resultado)
            except PermissionError as e:
                return self._responder_json(401, {"sucesso": False, "erro": str(e)})
            except Exception as e:
                return self._responder_erro(500, f"Erro interno: {e}")

        # Validação obrigatória de segurança para todas as demais ações
        if not self._verificar_autenticacao(rota):
            return

        # API: Logout / Encerrar sessão
        if rota == "/api/auth/logout":
            token = self._obter_token_requisicao()
            self.servicos.encerrar_sessao(token)
            return self._responder_json(200, {"sucesso": True, "mensagem": "Sessão encerrada com sucesso."})

        # API: Acionamento de abertura da porta
        if rota == "/api/porta/abrir":
            duracao = float(body.get("duracao", 3.5))
            resultado = self.servicos.abrir_porta(origem="WEB", duracao=duracao)
            return self._responder_json(200, resultado)

        # API: Alternância de modo (PRODUÇÃO vs CADASTRO)
        if rota == "/api/modo":
            novo_modo = str(body.get("modo", "")).strip()
            try:
                resultado = self.servicos.alternar_modo(novo_modo)
                return self._responder_json(200, resultado)
            except ValueError as e:
                return self._responder_erro(400, str(e))

        # API: Leitura / Identificação de tag RFID
        if rota in ("/api/leitor/identificar", "/api/leitor/simular", "/api/leitor/ler"):
            uid = body.get("uid", "").strip()
            if not uid:
                return self._responder_erro(400, "Informe o UID do cartão RFID.")
            try:
                resultado = self.servicos.processar_tag(uid)
                return self._responder_json(200, resultado)
            except (ErroDatabase, ValueError) as e:
                return self._responder_erro(400, str(e))

        # API: Captura direta no leitor de hardware físico (se presente)
        if rota == "/api/leitor/capturar":
            timeout = float(body.get("timeout", 30.0))
            try:
                uid = self.servicos.capturar_tag_leitor_hardware(timeout=timeout)
                resultado = self.servicos.processar_tag(uid)
                return self._responder_json(200, resultado)
            except ErroModoBloqueado as e:
                return self._responder_erro(403, str(e))
            except TimeoutError as e:
                return self._responder_erro(408, str(e))
            except Exception as e:
                return self._responder_erro(500, f"Erro no leitor de hardware: {e}")

        # API: Cadastrar novo membro
        if rota == "/api/usuarios":
            try:
                resultado = self.servicos.cadastrar_usuario(
                    id_usuario=body.get("id"),
                    nome=body.get("nome"),
                    uid_cartao=body.get("uid_cartao"),
                    ativo=body.get("ativo", True),
                )
                return self._responder_json(201, resultado)
            except (ErroDatabase, ValueError) as e:
                return self._responder_erro(400, str(e))

        # API: Trocar cartão RFID
        if rota.startswith("/api/usuarios/") and rota.endswith("/trocar-cartao"):
            id_usuario = rota.split("/")[3]
            novo_uid = str(body.get("novo_uid", "")).strip()
            try:
                resultado = self.servicos.trocar_cartao(id_usuario, novo_uid)
                return self._responder_json(200, resultado)
            except (ErroDatabase, ValueError) as e:
                return self._responder_erro(400, str(e))

        # API: Trocar nome do membro
        if rota.startswith("/api/usuarios/") and rota.endswith("/trocar-nome"):
            id_usuario = rota.split("/")[3]
            novo_nome = str(body.get("novo_nome", "")).strip()
            try:
                resultado = self.servicos.alterar_nome(id_usuario, novo_nome)
                return self._responder_json(200, resultado)
            except (ErroDatabase, ValueError) as e:
                return self._responder_erro(400, str(e))

        self._responder_erro(404, "Endpoint não encontrado.")

    # -------------------------------------------------------------------------
    # ROTAS PUT
    # -------------------------------------------------------------------------
    def do_PUT(self):
        url = urlparse(self.path)
        rota = url.path.rstrip("/")

        if not self._verificar_autenticacao(rota):
            return

        if rota.startswith("/api/usuarios/"):
            id_usuario = rota.split("/")[-1]
            try:
                body = self._ler_json_body()
                if "nome" in body and body["nome"]:
                    self.servicos.alterar_nome(id_usuario, body["nome"])
                if "uid_cartao" in body and body["uid_cartao"]:
                    self.servicos.trocar_cartao(id_usuario, body["uid_cartao"])
                if "ativo" in body and body["ativo"] is not None:
                    self.servicos.definir_status_usuario(id_usuario, body["ativo"])

                resultado = self.servicos.obter_usuario(id_usuario)
                return self._responder_json(200, {
                    "sucesso": True,
                    "mensagem": f"Cadastro de '{resultado['usuario']['nome']}' atualizado com sucesso!",
                    "usuario": resultado["usuario"],
                })
            except (ErroDatabase, ValueError) as e:
                return self._responder_erro(400, str(e))
            except Exception as e:
                return self._responder_erro(500, f"Erro interno: {e}")

        self._responder_erro(404, "Endpoint não encontrado.")

    # -------------------------------------------------------------------------
    # ROTAS PATCH
    # -------------------------------------------------------------------------
    def do_PATCH(self):
        url = urlparse(self.path)
        rota = url.path.rstrip("/")

        if not self._verificar_autenticacao(rota):
            return

        if rota.startswith("/api/usuarios/") and rota.endswith("/status"):
            id_usuario = rota.split("/")[3]
            try:
                body = self._ler_json_body()
                if "ativo" not in body:
                    return self._responder_erro(400, "Campo 'ativo' (booleano) é obrigatório.")
                resultado = self.servicos.definir_status_usuario(id_usuario, body["ativo"])
                return self._responder_json(200, resultado)
            except (ErroDatabase, ValueError) as e:
                return self._responder_erro(400, str(e))

        self._responder_erro(404, "Endpoint não encontrado.")

    # -------------------------------------------------------------------------
    # ROTAS DELETE
    # -------------------------------------------------------------------------
    def do_DELETE(self):
        url = urlparse(self.path)
        rota = url.path.rstrip("/")

        if not self._verificar_autenticacao(rota):
            return

        if rota.startswith("/api/usuarios/"):
            id_usuario = rota.split("/")[-1]
            try:
                resultado = self.servicos.remover_usuario(id_usuario)
                return self._responder_json(200, resultado)
            except (ErroDatabase, ValueError) as e:
                return self._responder_erro(400, str(e))

        self._responder_erro(404, "Endpoint não encontrado.")

    # -------------------------------------------------------------------------
    # UTILITÁRIOS
    # -------------------------------------------------------------------------
    def _servir_arquivo(self, caminho: Path):
        if not caminho.is_file():
            return self._responder_erro(404, "Arquivo não encontrado.")

        tipo, _ = mimetypes.guess_type(str(caminho))
        if tipo is None:
            tipo = "application/octet-stream"

        try:
            with open(caminho, "rb") as f:
                conteudo = f.read()
            self.send_response(200)
            self.send_header("Content-Type", f"{tipo}; charset=utf-8" if "text" in tipo or "json" in tipo or "javascript" in tipo else tipo)
            self.send_header("Content-Length", str(len(conteudo)))
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(conteudo)
        except Exception as e:
            self._responder_erro(500, f"Erro ao ler arquivo: {e}")


def obter_ips_locais() -> list[str]:
    """Descobre os endereços IPv4 reais das interfaces de rede ativas."""
    ips: list[str] = []

    # 1. Tenta obter o IP de rota de saída via socket UDP (sem envio real de pacotes)
    for host_teste in ("8.8.8.8", "1.1.1.1", "192.168.10.194", "172.32.0.100"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.2)
                s.connect((host_teste, 80))
                ip_saida = s.getsockname()[0]
                if ip_saida and not ip_saida.startswith("127.") and ip_saida not in ips:
                    ips.append(ip_saida)
                    break
        except Exception:
            pass

    # 2. Resolução através do hostname
    try:
        nome_host = socket.gethostname()
        for ip in socket.gethostbyname_ex(nome_host)[2]:
            if ip and not ip.startswith("127.") and ip not in ips:
                ips.append(ip)
    except Exception:
        pass

    # 3. Varredura direta das interfaces via ifconfig (Linux / Luckfox) ou ipconfig (Windows)
    try:
        cmd = ["ifconfig"] if sys.platform != "win32" else ["ipconfig"]
        saida = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=2).decode("latin-1", errors="ignore")
        padrao = r"inet (?:addr:)?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)" if sys.platform != "win32" else r"IPv4.*?: ([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)"
        for match in re.finditer(padrao, saida):
            ip_achado = match.group(1)
            if not ip_achado.startswith("127.") and ip_achado not in ips:
                ips.append(ip_achado)
    except Exception:
        pass

    return ips


def executar_servidor(porta: int = 8088, caminho_db: Path | str | None = None):
    """Inicializa e executa o servidor HTTP na porta especificada."""
    if caminho_db is None:
        caminho_db = PASTA_PROJETO / CAMINHO_DATABASE_PADRAO

    caminho_db = Path(caminho_db).resolve()
    caminho_db.parent.mkdir(parents=True, exist_ok=True)

    # Cria a instância da camada de serviços e injeta no RequisicaoHandler
    servicos = ServicosPorta(caminho_database=caminho_db)
    RequisicaoHandler.servicos = servicos

    servidor = None
    portas_tentar = [porta] if porta != 8080 else [8080, 8088, 8000, 5000, 8888]
    porta_usada = porta

    HTTPServer.allow_reuse_address = True
    for p in portas_tentar:
        try:
            servidor = HTTPServer(("0.0.0.0", p), RequisicaoHandler)
            porta_usada = p
            break
        except OSError:
            continue

    if servidor is None:
        raise RuntimeError(f"Não foi possível vincular o servidor às portas {portas_tentar}.")

    ips_locais = obter_ips_locais()

    print("=" * 65)
    print("  [*] SISTEMA PORTA GEAR - PAINEL DE CONTROLE SEGURO")
    print(f"  [+] Banco SQLite: {caminho_db}")
    print(f"  [+] Autenticação & Anti-Bypass: Ativado")
    print(f"  [+] Servidor local: http://localhost:{porta_usada}")
    if ips_locais:
        for ip_local in ips_locais:
            print(f"  [+] Link na rede local: http://{ip_local}:{porta_usada}")
    else:
        print(f"  [+] Na rede local: http://0.0.0.0:{porta_usada}")
    if porta_usada != porta:
        print(f"  [!] (Porta {porta} ja estava em uso, inicializado na porta {porta_usada})")
    print("=" * 65)
    print("Pressione Ctrl+C para encerrar o servidor.\n")

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor finalizado com sucesso.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Servidor Web Porta GEAR")
    parser.add_argument("--porta", type=int, default=8088, help="Porta HTTP (padrão: 8088)")
    parser.add_argument("--database", type=str, default=None, help="Caminho do banco SQLite")
    args = parser.parse_args()

    executar_servidor(porta=args.porta, caminho_db=args.database)
