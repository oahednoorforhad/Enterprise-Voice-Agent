class DomainException(Exception):
    """Base exception for all domain-level errors."""
    pass


class CustomerNotFoundError(DomainException):
    """Raised when a customer ID yields no results."""
    pass


class TicketNotFoundError(DomainException):
    """Raised when a ticket ID yields no results or belongs to another customer."""
    pass


class RateLimitError(DomainException):
    """Raised when a customer exceeds the rate limit for an action."""
    pass


class TicketCreateError(DomainException):
    """Raised when ticket creation fails validation or DB constraints."""
    pass
