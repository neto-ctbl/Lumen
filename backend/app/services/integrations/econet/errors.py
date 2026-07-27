from __future__ import annotations


class EconetParserError(ValueError):
    pass


class EconetUnexpectedContractError(EconetParserError):
    pass


class EconetAuthenticationPageDetectedError(EconetParserError):
    pass


class EconetCnaeValidationError(EconetParserError):
    pass


class EconetSessionError(RuntimeError):
    pass


class EconetSessionDisabledError(EconetSessionError):
    pass


class EconetSessionNotLoadedError(EconetSessionError):
    pass


class EconetSessionExpiredError(EconetSessionError):
    pass


class EconetSessionInvalidError(EconetSessionError, ValueError):
    pass


class EconetTransportError(EconetSessionError):
    pass


class EconetUnexpectedRedirectError(EconetSessionError):
    pass


class EconetUnexpectedContentTypeError(EconetSessionError):
    pass


class EconetUnexpectedResponseError(EconetSessionError):
    pass


class EconetHtmlDecodingError(EconetUnexpectedResponseError):
    pass
