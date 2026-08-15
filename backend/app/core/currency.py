import enum


class Currency(enum.StrEnum):
    """Every currency the API can read back.

    EUR is legacy: it is no longer offered anywhere (see CurrencyIn), but records
    created while it was still on the list keep it and have to stay loadable.
    """

    USD = "USD"
    EUR = "EUR"
    CNY = "CNY"
    RUB = "RUB"


class CurrencyIn(enum.StrEnum):
    """Currencies a new record may be created in. EUR is not one of them."""

    USD = "USD"
    CNY = "CNY"
    RUB = "RUB"
