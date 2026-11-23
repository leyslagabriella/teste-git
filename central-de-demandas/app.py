from flask import Flask, request, render_template, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
from datetime import datetime
import random

app = Flask(__name__)

# 1. Conexão com o banco central_demandas
def conectar_banco():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="biancaaraujo",
        database="central_demandas"
    )

# Garante que existe um usuário com senha criptografada (Hash) para login
def inicializar_usuario_padrao():
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        senha_segura = generate_password_hash("123456")
        sql = """
            INSERT IGNORE INTO usuarios (nome, matricula, senha_hash, tipo_usuario)
            VALUES ('Bianca Araujo', '2025120IIPI0047', %s, 'aluno')
        """
        cursor.execute(sql, (senha_segura,))
        conexao.commit()
        cursor.close()
        conexao.close()
    except Exception:
        pass

@app.route('/listar-solicitacoes', methods=['GET'])
def listar_solicitacoes():
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT s.protocolo, s.titulo, s.prioridade, s.coletiva,
                   COALESCE(u.nome, 'Usuário') AS nome_usuario,
                   COALESCE(u.turma, '') AS turma,
                   COALESCE(c.nome, 'Geral') AS nome_categoria,
                   COALESCE(st.nome, 'Aberta') AS nome_status
            FROM solicitacoes s
            LEFT JOIN usuarios u ON s.id_usuario = u.id_usuario
            LEFT JOIN categorias c ON s.id_categoria = c.id_categoria
            LEFT JOIN status_solicitacao st ON s.id_status = st.id_status
            ORDER BY s.id_solicitacao DESC
        """

        cursor.execute(sql)
        lista = cursor.fetchall()
        cursor.close()
        conexao.close()
        return jsonify(lista)
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro ao listar: {erro}"}), 500


# ==========================================
# FORMULÁRIO 1: LOGIN COM SEGURANÇA (HASH)
# ==========================================
@app.route('/login', methods=['POST'])
def login():
    dados = request.get_json() or request.form
    matricula = (dados.get('matricula') or '').strip()
    senha = (dados.get('senha') or '').strip()

    if not matricula or not senha:
        return jsonify({"erro": "Preencha matrícula e senha."}), 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("SELECT * FROM usuarios WHERE matricula = %s", (matricula,))
        usuario = cursor.fetchone()
        cursor.close()
        conexao.close()

        # Verifica senha com hash (ou texto simples caso seja usuário antigo de teste)
        if usuario and (check_password_hash(usuario['senha_hash'], senha) or usuario['senha_hash'] == senha):
            return jsonify({
                "mensagem": "Login realizado com sucesso!",
                "id_usuario": usuario['id_usuario'],
                "nome": usuario['nome'],
                "tipo_usuario": usuario['tipo_usuario']
            })
        return jsonify({"erro": "Matrícula ou senha incorretas!"}), 401
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro no banco: {erro}"}), 500

@app.route('/cadastrar-usuario', methods=['POST'])
def cadastrar_usuario():
    dados = request.get_json() or request.form
    nome = (dados.get('nome') or '').strip()
    matricula = (dados.get('matricula') or '').strip()
    senha = (dados.get('senha') or '').strip()
    tipo_usuario = (dados.get('tipo_usuario') or 'aluno').strip()

    if not nome or not matricula or not senha:
        return jsonify({"erro": "Preencha nome, matrícula e senha."}), 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        # Verifica se a matrícula já existe
        cursor.execute("SELECT id_usuario FROM usuarios WHERE matricula = %s", (matricula,))
        if cursor.fetchone():
            cursor.close()
            conexao.close()
            return jsonify({"erro": "Esta matrícula já está cadastrada!"}), 409

        # Criptografa a senha individual do usuário (Segurança)
        senha_criptografada = generate_password_hash(senha)

        cursor.execute("""
            INSERT INTO usuarios (nome, matricula, senha_hash, tipo_usuario)
            VALUES (%s, %s, %s, %s)
        """, (nome, matricula, senha_criptografada, tipo_usuario))

        conexao.commit()
        cursor.close()
        conexao.close()
        return jsonify({"mensagem": "Conta criada com sucesso! Agora você já pode entrar."})
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro ao cadastrar: {erro}"}), 500
 
    

# ==========================================
# TABELA 1 (SOLICITACOES): CADASTRAR, CONSULTAR, EDITAR E EXCLUIR
# ==========================================
@app.route('/salvar-solicitacao', methods=['POST'])
def salvar_solicitacao():
    nome = (request.form.get('nome') or '').strip()
    matricula = (request.form.get('matricula') or '').strip()
    curso = (request.form.get('curso') or '').strip()
    turma = (request.form.get('turma') or '').strip()
    nome_categoria = (request.form.get('nome_categoria') or 'Geral').strip()

    titulo = (request.form.get('titulo') or '').strip()
    descricao = (request.form.get('descricao') or '').strip()
    prazo = request.form.get('prazo') or None
    prioridade = request.form.get('prioridade') or 'Baixa'
    coletiva = 1 if request.form.get('coletiva') == '1' else 0

    if not titulo or not descricao:
        return "Erro de validação: Título e descrição são obrigatórios.", 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        # 1. Busca ou cria o Curso
        id_curso = None
        if curso:
            cursor.execute("SELECT id_curso FROM cursos WHERE nome_curso = %s", (curso,))
            res_curso = cursor.fetchone()
            if res_curso:
                id_curso = res_curso['id_curso']
            else:
                cursor.execute("INSERT INTO cursos (nome_curso) VALUES (%s)", (curso,))
                id_curso = cursor.lastrowid

        # 2. Busca ou cria o Usuário pela matrícula digitada
        id_usuario = 1
        if matricula and nome:
            cursor.execute("SELECT id_usuario FROM usuarios WHERE matricula = %s", (matricula,))
            res_user = cursor.fetchone()
            if res_user:
                id_usuario = res_user['id_usuario']
                cursor.execute("UPDATE usuarios SET nome = %s, id_curso = %s, turma = %s WHERE id_usuario = %s",
                               (nome, id_curso, turma, id_usuario))
            else:
                senha_padrao = generate_password_hash("123456")
                cursor.execute("""
                    INSERT INTO usuarios (nome, matricula, senha_hash, tipo_usuario, id_curso, turma)
                    VALUES (%s, %s, %s, 'aluno', %s, %s)
                """, (nome, matricula, senha_padrao, id_curso, turma))
                id_usuario = cursor.lastrowid

        # 3. Busca ou cria a Categoria clicada no chip
        cursor.execute("SELECT id_categoria FROM categorias WHERE nome = %s", (nome_categoria,))
        res_cat = cursor.fetchone()
        if res_cat:
            id_categoria = res_cat['id_categoria']
        else:
            cursor.execute("INSERT INTO categorias (nome, descricao) VALUES (%s, %s)",
                           (nome_categoria, f"Demandas de {nome_categoria}"))
            id_categoria = cursor.lastrowid

        # 4. Salva a Solicitação vinculada aos IDs reais
        protocolo = f"PROT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        data_criacao = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        id_status = 1

        sql = """
            INSERT INTO solicitacoes (
                protocolo, titulo, descricao, data_criacao, prazo,
                prioridade, coletiva, id_usuario, id_categoria, id_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores = (protocolo, titulo, descricao, data_criacao, prazo, prioridade, coletiva, id_usuario, id_categoria, id_status)
        cursor.execute(sql, valores)

        conexao.commit()
        cursor.close()
        conexao.close()
        return f"Solicitação registrada com sucesso! Protocolo: {protocolo}"
    except mysql.connector.Error as erro:
        return f"Erro ao salvar no banco: {erro}", 500

@app.route('/buscar-protocolo', methods=['GET'])
def buscar_protocolo():
    protocolo = request.args.get('protocolo', '').strip()
    if not protocolo:
        return jsonify({"erro": "Digite um protocolo válido."}), 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        sql = """
            SELECT s.id_solicitacao, s.protocolo, s.titulo, s.descricao, s.prioridade, s.coletiva,
                   DATE_FORMAT(s.data_criacao, '%d/%m/%Y %H:%i') AS data_criacao,
                   COALESCE(u.nome, 'Usuário') AS nome_usuario,
                   COALESCE(c.nome_curso, 'Curso não informado') AS nome_curso,
                   COALESCE(u.turma, '') AS turma,
                   COALESCE(st.nome, 'Aberta') AS nome_status
            FROM solicitacoes s
            LEFT JOIN usuarios u ON s.id_usuario = u.id_usuario
            LEFT JOIN cursos c ON u.id_curso = c.id_curso
            LEFT JOIN status_solicitacao st ON s.id_status = st.id_status
            WHERE s.protocolo = %s
        """

        cursor.execute(sql, (protocolo,))
        resultado = cursor.fetchone()

        if not resultado:
            cursor.close()
            conexao.close()
            return jsonify({"erro": "Protocolo não encontrado no banco."}), 404

        cursor.execute("""
            SELECT m.id_mensagem, m.conteudo,
                   DATE_FORMAT(m.data_envio, '%H:%i') AS hora,
                   COALESCE(u.nome, 'Usuário') AS nome
            FROM mensagens m
            LEFT JOIN usuarios u ON m.id_usuario = u.id_usuario
            WHERE m.id_solicitacao = %s
            ORDER BY m.id_mensagem ASC
        """, (resultado['id_solicitacao'],))
        resultado['mensagens'] = cursor.fetchall()

        cursor.close()
        conexao.close()
        return jsonify(resultado)
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro no banco: {erro}"}), 500

@app.route('/editar-solicitacao', methods=['POST'])
def editar_solicitacao():
    dados = request.get_json()
    protocolo = (dados.get('protocolo') or '').strip()
    nova_descricao = (dados.get('descricao') or '').strip()

    if not protocolo or not nova_descricao:
        return jsonify({"erro": "Preencha a nova descrição."}), 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        cursor.execute("UPDATE solicitacoes SET descricao = %s WHERE protocolo = %s", (nova_descricao, protocolo))
        conexao.commit()
        cursor.close()
        conexao.close()
        return jsonify({"mensagem": "Solicitação atualizada com sucesso!"})
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro ao editar: {erro}"}), 500

@app.route('/excluir-solicitacao', methods=['POST'])
def excluir_solicitacao():
    dados = request.get_json()
    protocolo = (dados.get('protocolo') or '').strip()

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        # Remove mensagens ligadas antes de apagar a solicitação (integridade referencial)
        cursor.execute("DELETE FROM mensagens WHERE id_solicitacao = (SELECT id_solicitacao FROM solicitacoes WHERE protocolo = %s)", (protocolo,))
        cursor.execute("DELETE FROM solicitacoes WHERE protocolo = %s", (protocolo,))
        conexao.commit()
        cursor.close()
        conexao.close()
        return jsonify({"mensagem": "Solicitação excluída com sucesso!"})
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro ao excluir: {erro}"}), 500

# ==========================================
# TABELA 2 (MENSAGENS): CADASTRAR, EDITAR E EXCLUIR
# ==========================================
@app.route('/mensagens', methods=['POST'])
def criar_mensagem():
    dados = request.get_json()
    id_solicitacao = dados.get('id_solicitacao')
    conteudo = (dados.get('conteudo') or '').strip()
    id_usuario = dados.get('id_usuario') or 1

    if not id_solicitacao or not conteudo:
        return jsonify({"erro": "Escreva uma mensagem antes de enviar."}), 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        cursor.execute("INSERT INTO mensagens (conteudo, id_usuario, id_solicitacao) VALUES (%s, %s, %s)", (conteudo, id_usuario, id_solicitacao))
        conexao.commit()
        cursor.close()
        conexao.close()
        return jsonify({"mensagem": "Mensagem enviada!"})
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro ao enviar mensagem: {erro}"}), 500

@app.route('/mensagens/editar', methods=['POST'])
def editar_mensagem():
    dados = request.get_json()
    id_mensagem = dados.get('id_mensagem')
    conteudo = (dados.get('conteudo') or '').strip()

    if not conteudo:
        return jsonify({"erro": "A mensagem não pode ficar vazia."}), 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        cursor.execute("UPDATE mensagens SET conteudo = %s WHERE id_mensagem = %s", (conteudo, id_mensagem))
        conexao.commit()
        cursor.close()
        conexao.close()
        return jsonify({"mensagem": "Mensagem editada!"})
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro ao editar mensagem: {erro}"}), 500

@app.route('/mensagens/excluir', methods=['POST'])
def excluir_mensagem():
    dados = request.get_json()
    id_mensagem = dados.get('id_mensagem')

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        cursor.execute("DELETE FROM mensagens WHERE id_mensagem = %s", (id_mensagem,))
        conexao.commit()
        cursor.close()
        conexao.close()
        return jsonify({"mensagem": "Mensagem excluída!"})
    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro ao excluir mensagem: {erro}"}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    inicializar_usuario_padrao()
    app.run(debug=True)



