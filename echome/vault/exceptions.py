class CannotUnsealVaultServerError(Exception):
    pass

class VaultIsSealedError(Exception):
    pass

class SecretDoesNotExistError(Exception):
    pass
