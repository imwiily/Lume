import json
from pathlib import Path


def render(data):
    template = Path(__file__).with_name("report.html").read_text(encoding="utf-8")
    # Escapa inclusive </script> de texto arbitrário do manuscrito.
    payload = json.dumps(data, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return template.replace("__REPORT_DATA__", payload)
