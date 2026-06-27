class AppError(Exception):
    """Base exception for application-level errors."""


class InvalidUserInputError(AppError):
    """Raised when user input cannot be interpreted as a URL."""

    code = "not_a_url"
    message = "Не понял ваш запрос, пожалуйста отправьте ссылку на сайт для проверки."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class InvalidUrlError(AppError):
    """Raised when user input looks like a URL but is malformed."""

    code = "invalid_url"
    message = (
        "Ссылка указана некорректно, пожалуйста отправьте адрес сайта "
        "в формате https://example.ru."
    )

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
