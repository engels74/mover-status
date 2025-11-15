"""Nox sessions for multi-environment testing and quality assurance."""

import nox


@nox.session(python=["3.14"])
def tests(session: nox.Session) -> None:
    """Run test suite with coverage reporting.

    Args:
        session: The nox session object.
    """
    session.run("uv", "sync", external=True)
    session.run(
        "pytest",
        "--cov=mover_status",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=html",
        "--cov-fail-under=80",
    )


@nox.session(python=["3.14"])
def lint(session: nox.Session) -> None:
    """Run ruff linting and formatting checks.

    Args:
        session: The nox session object.
    """
    session.run("uv", "sync", external=True)
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session(python=["3.14"])
def typecheck(session: nox.Session) -> None:
    """Run basedpyright type checking.

    Args:
        session: The nox session object.
    """
    session.run("uv", "sync", external=True)
    session.run("uvx", "basedpyright@latest", external=True)


@nox.session(python=["3.14"])
def format(session: nox.Session) -> None:
    """Auto-format code with ruff.

    Args:
        session: The nox session object.
    """
    session.run("uv", "sync", external=True)
    session.run("ruff", "check", ".", "--fix")
    session.run("ruff", "format", ".")


@nox.session(python=["3.14"])
def coverage(session: nox.Session) -> None:
    """Generate and display coverage report.

    Args:
        session: The nox session object.
    """
    session.run("uv", "sync", external=True)
    session.run("coverage", "report", "--show-missing")
    session.run("coverage", "html")
    session.log("Coverage report generated in htmlcov/index.html")


@nox.session(python=["3.14"])
def check_isolation(session: nox.Session) -> None:
    """Check that core modules don't reference specific providers.

    Enforces the architectural rule that core/, types/, and utils/
    directories must remain provider-agnostic.

    Args:
        session: The nox session object.
    """
    session.run("python3", "scripts/check_provider_isolation.py", external=True)
