from typing import Optional
import re

def validar_senha(senha: str) -> Optional[str]:
    """Retorna mensagem de erro ou None se válida."""
    if len(senha) < 8:
        return 'A senha deve ter pelo menos 8 caracteres.'
    if not re.search(r'[A-Z]', senha):
        return 'A senha deve conter pelo menos uma letra maiúscula.'
    if not re.search(r'[0-9]', senha):
        return 'A senha deve conter pelo menos um número.'
    if not re.search(r'[^A-Za-z0-9]', senha):
        return 'A senha deve conter pelo menos um caractere especial (ex: @, #, !).'
    return None
