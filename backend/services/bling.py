def gerar_url_autorizacao() -> str:
    import secrets
    client_id = os.getenv("BLING_CLIENT_ID")
    redirect_uri = os.getenv("BLING_REDIRECT_URI")
    state = secrets.token_hex(16)
    return (
        f"https://www.bling.com.br/Api/v3/oauth/authorize"
        f"?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&state={state}"
    )
