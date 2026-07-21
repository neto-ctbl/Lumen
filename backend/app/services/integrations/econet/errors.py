from __future__ import annotations


class EconetParserError(ValueError):
    pass


class EconetUnexpectedContractError(EconetParserError):
    pass


class EconetAuthenticationPageDetectedError(EconetParserError):
    pass


class EconetCnaeValidationError(EconetParserError):
    pass
