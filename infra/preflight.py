import os
import sys


class PreflightError(Exception):
    """Exception raised when required environment variables are missing."""
    pass


def check_env(
    required_vars: list[str | tuple[str, str]],
    optional_vars: list[str | tuple[str, str]] | None = None,
    default_help_fmt: str = "{var} is not set or is empty.",
) -> dict[str, str]:
    """
    Check if environment variables are set.
    Raises PreflightError if required variables are missing.
    Warns if optional variables are missing.
    """
    errors = []
    env_values = {}
    optional_vars = optional_vars or []

    for item in required_vars:
        if isinstance(item, tuple):
            var_name, help_msg = item
        else:
            var_name = item
            help_msg = default_help_fmt.format(var=var_name)

        value = os.getenv(var_name)
        if value is None or value.strip() == "":
            try:
                # Safely format in case the custom message includes {var}
                formatted_msg = help_msg.format(var=var_name)
            except KeyError:
                formatted_msg = help_msg
            errors.append(formatted_msg)
        else:
            env_values[var_name] = value

    for item in optional_vars:
        if isinstance(item, tuple):
            var_name, help_msg = item
        else:
            var_name = item
            help_msg = default_help_fmt.format(var=var_name)

        value = os.getenv(var_name)
        if value is None or value.strip() == "":
            try:
                formatted_msg = help_msg.format(var=var_name)
            except KeyError:
                formatted_msg = help_msg
            # Print warning immediately, but don't add to errors
            print(f"[?] WARNING: {formatted_msg}", file=sys.stderr)
        else:
            env_values[var_name] = value

    if errors:
        error_msg = (
            "\n" + "=" * 80 + "\n"
            + "PREFLIGHT CHECKS FAILED\n"
            + "One or more required variables must be set in your `.env` file:\n\n"
            + "\n".join(f"  [!] {msg}" for msg in errors)
            + "\n" + "=" * 80
        )
        raise PreflightError(error_msg)

    return env_values
