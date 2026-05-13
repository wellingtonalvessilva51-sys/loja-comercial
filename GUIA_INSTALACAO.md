# 🚀 GUIA DE IMPLANTAÇÃO — Sistema Comercial da Loja

Este guia te leva do zero ao sistema funcionando em produção.
Não precisa ser técnico — siga os passos na ordem.

---

## PASSO 1 — Configurar o Bling (5 min)

1. Acesse: **app.bling.com.br**
2. Vá em: `Preferências → API → Integrações`
3. Clique em **"Novo aplicativo"** e preencha:
   - Nome: `Sistema Comercial`
   - Redirect URI: `https://SEU_APP.railway.app/auth/bling/callback`
   (você vai substituir SEU_APP depois)
4. Copie o **Client ID** e **Client Secret** — vai precisar no Passo 3.

**Importante:** certifique-se de que o campo "Vendedor" dos pedidos
sempre está preenchido com o nome exato das suas vendedoras.

---

## PASSO 2 — Subir o código no GitHub (10 min)

1. Crie uma conta em **github.com** (se não tiver)
2. Clique em **"New repository"** → Nome: `loja-comercial` → Create
3. No seu computador, abra o Terminal (Mac/Linux) ou Prompt de Comando (Windows)
4. Execute os comandos abaixo (uma linha por vez):

```bash
cd loja-comercial/backend
git init
git add .
git commit -m "primeiro commit"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/loja-comercial.git
git push -u origin main
```

---

## PASSO 3 — Deploy no Railway (10 min)

1. Acesse **railway.app** → entre com sua conta GitHub
2. Clique em **"New Project" → "Deploy from GitHub repo"**
3. Selecione o repositório `loja-comercial`
4. O Railway vai detectar o Python automaticamente

### Adicionar as variáveis de ambiente:
No Railway, vá em **"Variables"** e adicione uma por uma:

| Variável | Valor |
|----------|-------|
| `BLING_CLIENT_ID` | (copiado do Passo 1) |
| `BLING_CLIENT_SECRET` | (copiado do Passo 1) |
| `BLING_REDIRECT_URI` | `https://SEU_APP.railway.app/auth/bling/callback` |
| `SECRET_KEY` | (qualquer texto longo e aleatório, ex: `MinhaLojaSecreta2024XYZ`) |
| `EMAIL_GERENTE` | seu e-mail |
| `SENHA_GERENTE` | uma senha forte |
| `META_PADRAO_MENSAL` | `12000` |
| `PERCENTUAL_COMISSAO` | `5` |

5. Copie a URL gerada pelo Railway (ex: `loja-comercial-production.railway.app`)
6. Volte no Bling e atualize o Redirect URI com essa URL real.

---

## PASSO 4 — Conectar o Bling (2 min)

1. Abra no navegador: `https://SEU_APP.railway.app/auth/bling`
2. O Bling vai pedir autorização — clique em **Autorizar**
3. Pronto! O sistema está conectado.

---

## PASSO 5 — Primeiro acesso e configuração (5 min)

1. Acesse: `https://SEU_APP.railway.app`
2. Faça login com o e-mail e senha que você configurou em SENHA_GERENTE
3. Vá em **"Sincronizar Bling"** para importar os pedidos
4. Vá em **"Nova Vendedora"** e cadastre cada vendedora:
   - O campo **"Nome da vendedora no Bling"** deve ser IDÊNTICO ao nome
     que aparece no campo Vendedor dos pedidos no Bling.

---

## ACESSO DAS VENDEDORAS

Cada vendedora acessa pelo **celular da loja** no navegador:
`https://SEU_APP.railway.app`

Elas fazem login com o e-mail e senha que você cadastrou para elas.
O sistema identifica automaticamente se é gerente ou vendedora
e mostra a tela correta.

---

## SINCRONIZAÇÃO AUTOMÁTICA

O sistema busca novos pedidos do Bling **a cada 1 hora** automaticamente.
Você também pode clicar em **"Sincronizar Bling"** a qualquer momento.

---

## SUPORTE E PRÓXIMOS PASSOS

Se travar em qualquer passo, anote o erro e me chame que a gente resolve.

**Fase 2 (próxima):** notificações WhatsApp e alertas de cliente inativo.
