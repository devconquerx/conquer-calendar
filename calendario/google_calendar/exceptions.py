class ServiceAccountNoConfiguradaError(Exception):
    """GOOGLE_SERVICE_ACCOUNT_FILE no apunta a un archivo válido."""


class EmailFueraDeDominioError(Exception):
    """El host no tiene un email impersonable por la service account."""


class GoogleApiTransitorioError(Exception):
    """Error transitorio del API de Google (uso interno; no se propaga al request)."""
