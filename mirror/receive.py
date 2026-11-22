"""Absolute SSH entry point: does not depend on the login working directory."""

import sys
from receiver.guard import run

try:
    sys.exit(run(sys.argv[1]))
except Exception:
    print(
        "Receção bloqueada. Verifica o destino e a configuração da app.",
        file=sys.stderr,
    )
    sys.exit(1)
