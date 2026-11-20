from flask import Flask, request, render_template, redirect, jsonify
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

# 2. Rota para CADASTRAR uma nova solicitação no MySQL
@app.route('/salvar-solicitacao', methods=['POST'])
def salvar_solicitacao():
    try:
        titulo = request.form.get('titulo')
        descricao = request.form.get('descricao')
        id_usuario = request.form.get('id_usuario') or 1
        id_categoria = request.form.get('id_categoria') or 1

        prazo = request.form.get('prazo') or None
        prioridade = request.form.get('prioridade') or 'Baixa'
        coletiva = 1 if request.form.get('coletiva') == '1' else 0

        protocolo = f"PROT-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        data_criacao = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        id_status = 1

        conexao = conectar_banco()
        cursor = conexao.cursor()

        sql = """
            INSERT INTO solicitacoes (
                protocolo, titulo, descricao, data_criacao, prazo,
                prioridade, coletiva, id_usuario, id_categoria, id_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        valores = (
            protocolo, titulo, descricao, data_criacao, prazo,
            prioridade, coletiva, id_usuario, id_categoria, id_status
        )

        cursor.execute(sql, valores)
        conexao.commit()

        cursor.close()
        conexao.close()

        return f"Solicitação registrada com sucesso! Protocolo: {protocolo}"

    except mysql.connector.Error as erro:
        return f"Erro ao salvar no banco de dados: {erro}", 500

# 3. Rota para CONSULTAR uma solicitação pelo protocolo
@app.route('/buscar-protocolo', methods=['GET'])
def buscar_protocolo():
    protocolo = request.args.get('protocolo', '').strip()
    if not protocolo:
        return jsonify({"erro": "Digite um protocolo válido."}), 400

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        sql = """
            SELECT s.protocolo, s.titulo, s.descricao, s.prioridade,
                   DATE_FORMAT(s.data_criacao, '%d/%m/%Y %H:%i') AS data_criacao,
                   u.nome AS nome_usuario,
                   st.nome AS nome_status
            FROM solicitacoes s
            JOIN usuarios u ON s.id_usuario = u.id_usuario
            JOIN status_solicitacao st ON s.id_status = st.id_status
            WHERE s.protocolo = %s
        """
        cursor.execute(sql, (protocolo,))
        resultado = cursor.fetchone()

        cursor.close()
        conexao.close()

        if resultado:
            return jsonify(resultado)
        else:
            return jsonify({"erro": "Protocolo não encontrado no banco de dados."}), 404

    except mysql.connector.Error as erro:
        return jsonify({"erro": f"Erro no banco: {erro}"}), 500

# 4. Rota principal que carrega o site
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)



