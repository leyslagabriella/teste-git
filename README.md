# Central de Demandas da Coordenação — IFPI Campus Paulistana

Sistema web desenvolvido para registrar, acompanhar e gerenciar demandas acadêmicas entre estudantes e a coordenação do curso.

## Tecnologias Utilizadas
* **Back-end:** Python 3 + Flask
* **Banco de Dados:** MySQL (`mysql-connector-python`)
* **Front-end:** HTML5, CSS3 e JavaScript

## Como configurar e rodar o projeto

### 1. Configurar o Banco de Dados (MySQL)
1. Abra o **MySQL Workbench** e conecte-se ao seu servidor local.
2. Execute o script SQL disponível no arquivo `banco_mysql.sql` para criar o banco `central_demandas`, todas as 8 tabelas e os registros iniciais obrigatórios (`categorias`, `status_solicitacao` e `usuarios`).
3. No arquivo `app.py`, localize a função `conectar_banco()` e coloque a sua senha do MySQL no campo `password`.

### 2. Instalar as dependências do Python
Abra o terminal na pasta do projeto e execute:
```bash
pip install flask mysql-connector-python
```

### 3. Iniciar o servidor
No terminal, rode o comando:
```bash
python app.py
```
Depois, abra o navegador e acesse: **`http://127.0.0.1:5000`**

## Funcionalidades Implementadas (Entrega 2)
* **Cadastro de Solicitações:** Formulário na *Área do Aluno* que salva os dados reais na tabela `solicitacoes` do MySQL gerando um código de protocolo único.
* **Consulta por Protocolo:** Busca na aba *Acompanhar* que consulta o banco de dados e exibe o título, descrição, solicitante, status e data da demanda.
*
