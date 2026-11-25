import os
import re
import hmac
import secrets
import logging

from datetime import timedelta
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from flask import (
    Flask,
    request,
    session,
    jsonify,
    abort,
    current_app,
    g
)

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from werkzeug.security import check_password_hash
from werkzeug.utils import secure_filename


logger = logging.getLogger("central_demandas.security")

TAMANHO_MAXIMO_UPLOAD = 5 * 1024 * 1024

EXTENSOES_PERMITIDAS = {
    "pdf",
    "png",
    "jpg",
    "jpeg"
}

MIMETYPES_PERMITIDOS = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg"
}

TIPOS_USUARIO = {
    "aluno",
    "coordenador",
    "administrador"
}

METODOS_INSEGUROS = {
    "POST",
    "PUT",
    "PATCH",
    "DELETE"
}


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=os.getenv(
        "RATELIMIT_STORAGE_URI",
        "memory://"
    ),
    strategy="fixed-window"
)



def configurar_seguranca(app: Flask):

    secret_key = os.getenv("FLASK_SECRET_KEY")

    if not secret_key:
        raise RuntimeError(
            "FLASK_SECRET_KEY não configurada."
        )

    if len(secret_key) < 32:
        raise RuntimeError(
            "FLASK_SECRET_KEY deve possuir pelo menos 32 caracteres."
        )

    app.secret_key = secret_key

    app.config.update(

        # Sessões
        SESSION_COOKIE_NAME="central_demandas_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SECURE=os.getenv(
            "COOKIE_SECURE",
            "true"
        ).lower() == "true",
        SESSION_COOKIE_SAMESITE="Lax",

        PERMANENT_SESSION_LIFETIME=timedelta(
            minutes=20
        ),

        SESSION_REFRESH_EACH_REQUEST=True,

        # Upload
        MAX_CONTENT_LENGTH=TAMANHO_MAXIMO_UPLOAD,

        # JSON
        JSON_SORT_KEYS=False,

        # Proteções
        TRUSTED_HOSTS=[
            host.strip()
            for host in os.getenv(
                "TRUSTED_HOSTS",
                ""
            ).split(",")
            if host.strip()
        ] or None
    )

    limiter.init_app(app)

    registrar_protecoes(app)

    return app



def registrar_protecoes(app):

    @app.after_request
    def adicionar_cabecalhos(response):

        response.headers["X-Content-Type-Options"] = "nosniff"

        response.headers["X-Frame-Options"] = "DENY"

        response.headers["Referrer-Policy"] = (
            "strict-origin-when-cross-origin"
        )

        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )

        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )

        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, private"
        )

        response.headers["Pragma"] = "no-cache"

        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        if request.is_secure:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )

        return response

    @app.errorhandler(413)
    def arquivo_grande(error):

        return jsonify({
            "erro": "O arquivo ultrapassa o limite permitido."
        }), 413

    @app.errorhandler(429)
    def limite_excedido(error):

        return jsonify({
            "erro": "Muitas tentativas. Aguarde antes de tentar novamente."
        }), 429


def usuario_autenticado():

    return (
        isinstance(session.get("usuario_id"), int)
        and session.get("usuario_id") > 0
        and session.get("usuario_tipo") in TIPOS_USUARIO
    )


def exigir_login(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if not usuario_autenticado():

            session.clear()

            return jsonify({
                "erro": "Autenticação necessária."
            }), 401

        g.usuario_id = session["usuario_id"]
        g.usuario_tipo = session["usuario_tipo"]

        return func(*args, **kwargs)

    return wrapper


def exigir_tipo_usuario(*tipos_permitidos):

    tipos = set(tipos_permitidos)

    if not tipos or not tipos.issubset(TIPOS_USUARIO):
        raise ValueError("Tipo de usuário inválido.")

    def decorator(func):

        @wraps(func)
        @exigir_login
        def wrapper(*args, **kwargs):

            if session.get("usuario_tipo") not in tipos:

                return jsonify({
                    "erro": "Você não possui permissão para esta operação."
                }), 403

            return func(*args, **kwargs)

        return wrapper

    return decorator



def iniciar_sessao_segura(usuario):

    if not isinstance(usuario, dict):
        raise ValueError("Usuário inválido.")

    usuario_id = usuario.get("id_usuario")

    tipo = usuario.get("tipo")

    if tipo not in TIPOS_USUARIO:
        raise ValueError("Tipo de usuário inválido.")

    if not isinstance(usuario_id, int) or usuario_id <= 0:
        raise ValueError("Identificador de usuário inválido.")

    session.clear()

    session.permanent = True

    session["usuario_id"] = usuario_id
    session["usuario_tipo"] = tipo

    session["csrf_token"] = secrets.token_urlsafe(32)

    session["sessao_criada"] = True

    return True


def encerrar_sessao():

    session.clear()



def gerar_token_csrf():

    if "csrf_token" not in session:

        session["csrf_token"] = secrets.token_urlsafe(32)

    return session["csrf_token"]


def validar_csrf():

    token_sessao = session.get("csrf_token")

    token_recebido = (
        request.headers.get("X-CSRF-Token")
        or request.form.get("csrf_token")
    )

    if not token_sessao or not token_recebido:
        return False

    if not isinstance(token_recebido, str):
        return False

    return hmac.compare_digest(
        token_sessao,
        token_recebido
    )


def exigir_csrf(func):

    @wraps(func)
    def wrapper(*args, **kwargs):

        if request.method in METODOS_INSEGUROS:

            if not validar_csrf():

                return jsonify({
                    "erro": "Token CSRF inválido ou ausente."
                }), 403

        return func(*args, **kwargs)

    return wrapper




def validar_origem():

    origem = request.headers.get("Origin")

    if not origem:
        return True

    try:
        origem_url = urlparse(origem)

        host_origem = origem_url.netloc.lower()

        host_atual = request.host.lower()

        esquema_origem = origem_url.scheme.lower()

        esquema_atual = (
            "https" if request.is_secure else "http"
        )

        return (
            host_origem == host_atual
            and esquema_origem == esquema_atual
        )

    except Exception:

        return False


def validar_texto(
    texto,
    minimo=1,
    maximo=5000,
    obrigatorio=True
):

    if texto is None:

        if obrigatorio:
            raise ValueError("Campo obrigatório.")

        return None

    if not isinstance(texto, str):
        raise ValueError("Formato de texto inválido.")

    texto = texto.strip()

    if obrigatorio and not texto:
        raise ValueError("Campo obrigatório.")

    if len(texto) < minimo:
        raise ValueError("Texto muito curto.")

    if len(texto) > maximo:
        raise ValueError("Texto muito grande.")

    if "\x00" in texto:
        raise ValueError("Texto inválido.")

    return texto



def validar_matricula(matricula):

    if not isinstance(matricula, str):
        return False

    matricula = matricula.strip()

    return bool(
        re.fullmatch(r"[A-Za-z0-9]{4,20}", matricula)
    )


def validar_senha(senha):

    if not isinstance(senha, str):
        return False

    if len(senha) < 10:
        return False

    if len(senha) > 128:
        return False

    if not any(c.isupper() for c in senha):
        return False

    if not any(c.islower() for c in senha):
        return False

    if not any(c.isdigit() for c in senha):
        return False

    return True




def verificar_senha(senha, hash_senha):

    if not isinstance(senha, str):
        return False

    if not isinstance(hash_senha, str):
        return False

    try:

        return check_password_hash(
            hash_senha,
            senha
        )

    except (ValueError, TypeError):

        return False



def validar_protocolo(protocolo):

    if not isinstance(protocolo, str):
        return False

    return bool(
        re.fullmatch(
            r"[A-Z0-9-]{6,30}",
            protocolo
        )
    )



def obter_json_validado():

    if not request.is_json:
        abort(415)

    dados = request.get_json(silent=True)

    if not isinstance(dados, dict):
        abort(400)

    return dados

def validar_extensao(nome):

    if not isinstance(nome, str):
        return False

    if "." not in nome:
        return False

    extensao = nome.rsplit(".", 1)[1].lower()

    return extensao in EXTENSOES_PERMITIDAS


def validar_assinatura_arquivo(arquivo, extensao):

    arquivo.seek(0)

    assinatura = arquivo.read(16)

    arquivo.seek(0)

    assinaturas = {

        "pdf": (
            assinatura.startswith(b"%PDF-")
        ),

        "png": (
            assinatura.startswith(
                b"\x89PNG\r\n\x1a\n"
            )
        ),

        "jpg": (
            assinatura.startswith(b"\xff\xd8\xff")
        ),

        "jpeg": (
            assinatura.startswith(b"\xff\xd8\xff")
        )
    }

    return assinaturas.get(extensao, False)


def validar_upload(arquivo):

    if not arquivo:
        raise ValueError("Nenhum arquivo enviado.")

    nome_original = arquivo.filename

    if not nome_original:
        raise ValueError("Nome do arquivo inválido.")

    if not validar_extensao(nome_original):
        raise ValueError("Extensão não permitida.")

    nome_seguro = secure_filename(nome_original)

    if not nome_seguro:
        raise ValueError("Nome do arquivo inválido.")

    extensao = nome_seguro.rsplit(".", 1)[1].lower()

    arquivo.seek(0, os.SEEK_END)

    tamanho = arquivo.tell()

    arquivo.seek(0)

    if tamanho <= 0:
        raise ValueError("Arquivo vazio.")

    if tamanho > TAMANHO_MAXIMO_UPLOAD:
        raise ValueError("Arquivo muito grande.")

    if not validar_assinatura_arquivo(
        arquivo,
        extensao
    ):
        raise ValueError("Conteúdo do arquivo inválido.")

    return {
        "nome_original": nome_seguro,
        "extensao": extensao,
        "mime": MIMETYPES_PERMITIDOS[extensao],
        "tamanho": tamanho
    }



def salvar_upload_seguro(arquivo, pasta):

    dados = validar_upload(arquivo)

    pasta_destino = Path(pasta).resolve()

    pasta_destino.mkdir(
        parents=True,
        exist_ok=True
    )

    nome_aleatorio = (
        secrets.token_hex(24)
        + "."
        + dados["extensao"]
    )

    caminho = (pasta_destino / nome_aleatorio).resolve()

    if caminho.parent != pasta_destino:
        raise ValueError("Caminho de arquivo inválido.")

    arquivo.save(caminho)

    return {
        **dados,
        "nome_armazenado": nome_aleatorio,
        "caminho": str(caminho)
    }



def limitar_tentativas_login(func):

    @wraps(func)
    @limiter.limit("5 per minute")
    @limiter.limit("20 per hour")
    def wrapper(*args, **kwargs):

        return func(*args, **kwargs)

    return wrapper


def usuario_pode_acessar_recurso(
    proprietario_id
):

    if not usuario_autenticado():
        return False

    tipo = session.get("usuario_tipo")

    if tipo in {
        "coordenador",
        "administrador"
    }:
        return True

    return (
        session.get("usuario_id")
        == proprietario_id
    )

def registrar_evento_seguranca(
    evento,
    nivel="warning"
):

    eventos_permitidos = {
        "login_falhou",
        "login_sucesso",
        "acesso_negado",
        "csrf_invalido",
        "upload_rejeitado",
        "sessao_encerrada",
        "tentativa_suspeita"
    }

    if evento not in eventos_permitidos:
        return

    dados = {
        "evento": evento,
        "ip": get_remote_address(),
        "metodo": request.method,
        "rota": request.path
    }

    mensagem = (
        "Evento de segurança: %s"
        % dados
    )

    if nivel == "error":
        logger.error(mensagem)

    elif nivel == "info":
        logger.info(mensagem)

    else:
        logger.warning(mensagem)
