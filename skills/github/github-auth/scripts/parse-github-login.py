#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

try:
    with open(sys.argv[1], "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    sys.exit(0)
login = data.get("login", "")
if login:
    print(login)
