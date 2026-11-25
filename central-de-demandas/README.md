#Central de Demandas Estudantis — IFPI Campus Paulistana

Sistema web desenvolvido para a disciplina de **Programação Avançada para Web** (IFPI — Campus Paulistana), com o objetivo de centralizar, priorizar e acompanhar solicitações acadêmicas e administrativas enviadas pelos estudantes à Coordenação de Curso.

---

## 🎯 Objetivo do Projeto

Substituir atendimentos informais e dispersos por um fluxo organizado com geração de protocolo único, cálculo automático de prioridade (individual ou coletiva da turma), histórico de comunicação integrado e painel gerencial para a coordenação.

---

## Tecnologias Utilizadas

* **Back-end:** Python 3 com **Flask**
* **Front-end:** HTML5, CSS3 e JavaScript (Fetch API)
* **Banco de Dados:** MySQL 8 (`central_demandas`)
* **Segurança:** `werkzeug.security` (Hash `scrypt`), `secrets` (Token CSRF), Expressões Regulares (`re`) e Queries Parametrizadas (`mysql-connector-python`)

---

## Funcionalidades Implementadas

### 1. Autenticação e Controle de Acesso (RBAC)
* **Cadastro e Login com Senha Individual:** Cada usuário cria sua própria senha (mínimo 6 caracteres), armazenada com hash criptográfico irreversível (`scrypt` + salt).
* **Identificação Automática pelo Padrão SUAP:** O sistema valida o formato da matrícula via expressão regular (`regex`) e define automaticamente o nível de permissão:
  * **Estudante (`aluno`):** Matrícula acadêmica alfanumérica (ex: `2025120IIPI0047`). Acessa apenas a abertura e o acompanhamento de solicitações.
  * **Coordenação / Servidor (`coordenador`):** Matrícula SIAPE de 7 dígitos numéricos (ex: `2044342`). Acessa o Painel da Coordenação, a fila geral de demandas e o histórico de atendimento.

### 2. Formulários com Validação e Segurança
* **Login e Cadastro de Usuários:** Conferência de campos obrigatórios, tamanho mínimo de senha e formato de matrícula SUAP.
* **Nova Solicitação:** Registro de demandas individuais ou **coletivas da turma**, seleção de categoria, cálculo automático de prioridade (**Alta**, **Média** ou **Baixa**), proteção contra CSRF (`csrf_token` na sessão) e upload de documentos comprobatórios (**PDF, PNG, JPG**).
* **Consulta e Chat de Comunicação:** Busca por número de protocolo com exibição de anexos (download/visualização) e troca de mensagens em tempo real entre aluno e coordenação.

### 3. Operações CRUD em Tabelas Relacionadas
O sistema realiza operações completas de **Cadastrar (`INSERT`)**, **Consultar (`SELECT`)**, **Editar (`UPDATE`)** e **Excluir (`DELETE`)** integradas entre tabelas ligadas por chaves estrangeiras (`FOREIGN KEY`):
* **Tabela `solicitacoes`:** Criação de demandas com protocolo único (`PROT-AAAAMMDD-XXXX`), consulta detalhada com `LEFT JOIN` (`usuarios`, `cursos`, `categorias`, `status_solicitacao`), edição da descrição e exclusão da solicitação.
* **Tabela `mensagens` (ligada via `id_solicitacao`):** Envio, listagem cronológica, edição e exclusão de mensagens vinculadas a cada protocolo.
* **Tabela `anexos` (ligada via `id_solicitacao`):** Upload de arquivos armazenados em `static/uploads/` e vinculação automática ao protocolo.

### 4. Painel da Coordenação
* **Indicadores em Tempo Real (KPIs):** Contagem automática de solicitações abertas, por nível de prioridade (Alta, Média, Baixa), em andamento e resolvidas diretamente do MySQL.
* **Fila Inteligente:** Listagem dinâmica das demandas com destaque visual para **Solicitações Coletivas da Turma**, filtro por prioridade e acesso rápido ao atendimento.

---

## Cuidados de Segurança Aplicados

1. **Criptografia de Senhas (`scrypt`):** Uso de `generate_password_hash` e `check_password_hash` para impedir armazenamento de senhas em texto puro.
2. **Proteção contra SQL Injection:** Todas as consultas SQL utilizam *Prepared Statements* / queries parametrizadas (`%s`).
3. **Proteção CSRF (Código Secreto do Formulário):** Geração de token único por sessão (`secrets.token_hex`) validado no envio de solicitações.
4. **Validação no Servidor e Prevenção de Escalada de Privilégio:** Bloqueio de entradas vazias e atribuição automática de perfil baseada no padrão oficial de matrícula do SUAP.

---

## Estrutura do Banco de Dados (`central_demandas`)

O banco relacional é composto pelas seguintes tabelas integradas:
* `cursos` — Cursos ofertados no campus
* `usuarios` — Alunos e coordenadores cadastrados (`matricula`, `senha_hash`, `tipo_usuario`, `id_curso`, `turma`)
* `categorias` — Tipos de demanda (Matrícula, Professores, Documentação, Infraestrutura, etc.)
* `status_solicitacao` — Etapas do fluxo de atendimento (Aberta, Em Análise, Em Andamento, Resolvida)
* `solicitacoes` — Tabela principal com protocolos, prioridades e flag `coletiva`
* `mensagens` — Histórico do chat vinculado à solicitação (`id_solicitacao`) e ao autor (`id_usuario`)
* `anexos` — Arquivos comprobatórios vinculados à solicitação (`id_solicitacao`)
* `historico_status` — Log de movimentações de status

---

##  Como Instalar e Rodar Localmente

### Pré-requisitos
* **Python 3.10+** instalado
* **MySQL Server** (e MySQL Workbench) em execução

### Passo 1: Clonar o repositório
```bash
git clone https://github.com
cd teste-git
```

### Passo 2: Configurar o Banco de Dados
1. Abra o **MySQL Workbench** e conecte-se ao servidor local.
2. Execute o script SQL do projeto (`central_demandas.sql`) para criar o banco de dados `central_demandas` e suas tabelas.
3. Confira no arquivo `app.py` (função `conectar_banco`) se `user` e `password` correspondem à sua instância local do MySQL.

### Passo 3: Instalar as dependências Python
```bash
pip install flask mysql-connector-python werkzeug
```

### Passo 4: Iniciar o servidor
```bash
python app.py
```
Acesse no navegador: **`http://127.0.0.1:5000`**

---

## 🧪 Credenciais e Padrões de Teste

* **Cadastro de Estudante:** Utilize uma matrícula no padrão acadêmico do IFPI (ex: `2025120IIPI0047`) e senha com 6 ou mais caracteres.
* **Cadastro de Coordenação:** Utilize uma matrícula SIAPE de 7 dígitos numéricos (ex: `2044342`) e senha com 6 ou mais caracteres.
