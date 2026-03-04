# Registro Próprio - Plataforma completa

Projeto one-page com página dedicada **Proteja sua criação**, banco de dados, autenticação e checkout Stripe.

## Recursos implementados
- Copy e identidade visual originais (cores e textos novos).
- Landing page única (`/`) + página de formulário (`/proteja`).
- Cadastro e login com e-mail/senha.
- Login social com Google.
- Banco SQLite para usuários e criações.
- Planos com **10% de desconto**:
  - Solo: de R$ 25,00 para R$ 22,50
  - Budget: de R$ 40,00 para R$ 36,00
  - Creator: de R$ 68,00 para R$ 61,20
  - Studio: de R$ 112,00 para R$ 100,80
- Botão **Concluir** na página `/proteja` redireciona para Stripe Checkout.

## Execução
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask --app app run --debug
```

Acesse: `http://127.0.0.1:5000`

## Configuração Google Login
1. Crie credenciais OAuth no Google Cloud.
2. Redirect URI: `http://127.0.0.1:5000/auth/google/callback`
3. Preencha `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` no `.env`.

## Configuração Stripe
1. Crie 4 produtos/preços no Stripe.
2. Preencha `STRIPE_PRICE_*` no `.env`.
3. Com `STRIPE_SECRET_KEY` + prices configurados, o botão **Concluir** abre o checkout.
