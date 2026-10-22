```python
import os
import re
import secrets
import logging
from pathlib import Path
from functools import wraps
from datetime import timedelta
from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename
from flask import (
    Flask,
    request,
    session,
    jsonify,
    abort,
    current_app
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


BASE_DIR = Path(__file__).resolve().parent

UPLOAD_DIR = BASE_DIR / "uploads"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

EXTENSOES_PERMITIDAS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "doc",
    "docx"
}

TAMANHO_MAXIMO_ARQUIVO = 5 * 1024 * 1024

PROTOCOLO_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,50}$")

MATRICULA_REGEX = re.compile(r"^[A-Za-z0-9_-]{1,30}$")

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("central_de_demandas")


def gerar_chave_secreta():
    chave = os.getenv("FLASK_SECRET_KEY")

    if not chave or len(chave) < 32:
        raise RuntimeError(
            "Configure FLASK_SECRET_KEY com uma chave aleatoria "
            "forte de pelo menos 32 caracteres."
        )

    return chave


def configurar_seguranca(app: Flask):
    app.config["SECRET_KEY"] = gerar_chave_secreta()

    app.config["MAX_CONTENT_LENGTH"] = TAMANHO_MAXIMO_ARQUIVO

    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.getenv("HTTPS_ATIVO", "false").lower() == "true"
    )

    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(minutes=30)

    app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per day", "60 per hour"],
        storage_uri=os.getenv(
            "RATELIMIT_STORAGE_URI",
            "memory://"
        )
    )

    limiter.init_app(app)

    @app.before_request
    def verificar_requisicao():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origem = request.headers.get("Origin")

            if origem:
                origem_host = request.host_url.rstrip("/")
                if origem.rstrip("/") != origem_host:
                    abort(403, description="Origem da requisicao invalida.")

    @app.after_request
    def adicionar_cabecalhos_seguranca(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'"
        )
        response.headers["Cache-Control"] = "no-store"

        if request.is_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response

    @app.errorhandler(413)
    def arquivo_muito_grande(error):
        return jsonify({
            "erro": "O arquivo excede o tamanho permitido."
        }), 413

    @app.errorhandler(429)
    def muitas_requisicoes(error):
        return jsonify({
            "erro": "Muitas requisicoes. Tente novamente mais tarde."
        }), 429

    return limiter


def exigir_login(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if not session.get("usuario_id"):
            return jsonify({
                "erro": "Autenticacao necessaria."
            }), 401

        return funcao(*args, **kwargs)

    return wrapper


def exigir_tipo_usuario(*tipos_permitidos):
    def decorador(funcao):
        @wraps(funcao)
        def wrapper(*args, **kwargs):
            if not session.get("usuario_id"):
                return jsonify({
                    "erro": "Autenticacao necessaria."
                }), 401

            tipo = session.get("tipo_usuario")

            if tipo not in tipos_permitidos:
                return jsonify({
                    "erro": "Voce nao tem permissao para esta operacao."
                }), 403

            return funcao(*args, **kwargs)

        return wrapper

    return decorador


def validar_texto(valor, tamanho_maximo=2000):
    if not isinstance(valor, str):
        return False

    valor = valor.strip()

    if not valor or len(valor) > tamanho_maximo:
        return False

    if "\x00" in valor:
        return False

    return True


def validar_matricula(matricula):
    if not isinstance(matricula, str):
        return False

    return bool(MATRICULA_REGEX.fullmatch(matricula.strip()))


def validar_protocolo(protocolo):
    if not isinstance(protocolo, str):
        return False

    return bool(PROTOCOLO_REGEX.fullmatch(protocolo.strip()))


def verificar_senha(senha_hash, senha_informada):
    if not isinstance(senha_hash, str):
        return False

    if not isinstance(senha_informada, str):
        return False

    try:
        return check_password_hash(senha_hash, senha_informada)
    except (ValueError, TypeError):
        return False


def iniciar_sessao_segura(usuario):
    session.clear()

    session["usuario_id"] = usuario["id_usuarios"]
    session["tipo_usuario"] = usuario["tipo_usuario"]

    session.permanent = True

    session["csrf_token"] = secrets.token_urlsafe(32)


def encerrar_sessao_segura():
    session.clear()


def obter_token_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


def exigir_csrf(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return funcao(*args, **kwargs)

        token_sessao = session.get("csrf_token")
        token_recebido = request.headers.get("X-CSRF-Token")

        if not token_sessao or not token_recebido:
            return jsonify({
                "erro": "Token de seguranca ausente."
            }), 403

        if not secrets.compare_digest(token_sessao, token_recebido):
            return jsonify({
                "erro": "Token de seguranca invalido."
            }), 403

        return funcao(*args, **kwargs)

    return wrapper


def validar_upload(arquivo):
    if not arquivo or not arquivo.filename:
        return False, "Nenhum arquivo foi enviado."

    nome_seguro = secure_filename(arquivo.filename)

    if not nome_seguro or "." not in nome_seguro:
        return False, "Nome de arquivo invalido."

    extensao = nome_seguro.rsplit(".", 1)[1].lower()

    if extensao not in EXTENSOES_PERMITIDAS:
        return False, "Tipo de arquivo nao permitido."

    conteudo = arquivo.stream.read(TAMANHO_MAXIMO_ARQUIVO + 1)
    arquivo.stream.seek(0)

    if len(conteudo) > TAMANHO_MAXIMO_ARQUIVO:
        return False, "O arquivo excede o limite de 5 MB."

    assinaturas = {
        "pdf": (b"%PDF-",),
        "png": (b"\x89PNG\r\n\x1a\n",),
        "jpg": (b"\xff\xd8\xff",),
        "jpeg": (b"\xff\xd8\xff",),
        "doc": (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",),
        "docx": (b"PK\x03\x04",)
    }

    assinaturas_validas = assinaturas.get(extensao, ())

    if not any(
        conteudo.startswith(assinatura)
        for assinatura in assinaturas_validas
    ):
        return False, "O conteudo nao corresponde ao tipo do arquivo."

    nome_armazenamento = secrets.token_hex(16) + "." + extensao

    return True, nome_armazenamento


def salvar_upload_seguro(arquivo):
    valido, resultado = validar_upload(arquivo)

    if not valido:
        return None, resultado

    destino = UPLOAD_DIR / resultado

    try:
        arquivo.save(destino)
    except OSError:
        logger.exception("Falha ao salvar anexo.")
        return None, "Nao foi possivel salvar o arquivo."

    return resultado, None


def validar_json_obrigatorio(*campos):
    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        return None, (
            jsonify({"erro": "Corpo JSON invalido."}),
            400
        )

    faltantes = [
        campo for campo in campos
        if campo not in dados
        or dados[campo] is None
        or (
            isinstance(dados[campo], str)
            and not dados[campo].strip()
        )
    ]

    if faltantes:
        return None, (
            jsonify({
                "erro": "Existem campos obrigatorios ausentes.",
                "campos": faltantes
            }),
            400
        )

    return dados, None


def registrar_evento_seguranca(evento, detalhes=None):
    logger.warning(
        "Evento de seguranca: %s | detalhes=%s",
        evento,
        detalhes or "nenhum"
    )
```
