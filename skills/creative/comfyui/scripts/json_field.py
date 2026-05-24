#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

if len(sys.argv) != 3:
    sys.exit(2)
path, key = sys.argv[1:]
try:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
except Exception:
    sys.exit(0)
value = data.get(key, "")
if value is None:
    value = ""
print(value)
