"""Integração CLI/JSON para a interface Swift. Usa o Python com dependências instaladas."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from docx import Document

ROOT = Path(__file__).resolve().parents[1]

def main():
    with tempfile.TemporaryDirectory(prefix="fonte contrato ") as temporary:
        folder = Path(temporary)
        document = folder / "Livro d'Água $(literal).docx"
        doc = Document()
        doc.add_paragraph("Capítulo 1")
        doc.add_paragraph("🌿 Cafe\u0301. Clara abriu a janela e observa a rua.")
        doc.add_paragraph("Uma velha cadeira de madeira no canto da sala.")
        doc.save(document)
        original = document.read_bytes()
        output = folder / "saída inédita"
        result = subprocess.run(
            [sys.executable, "-u", "-m", "fonte", "revisar", str(document),
             "--saida", str(output), "--tempo", "passado"],
            cwd=ROOT / "fonte", capture_output=True, text=True, timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        report = json.loads((output / "relatorio.json").read_text())
        assert document.read_bytes() == original, "O original mudou"
        assert report["schema_version"] == 1
        assert report["sha256"] == hashlib.sha256(original).hexdigest()
        assert report["metadata"]["versao_fonte"] == "1.2.1"
        assert isinstance(report["metadata"]["paragrafos"], int)
        assert isinstance(report["metadata"]["languagetool"], bool)
        ids = set()
        for finding in report["findings"]:
            assert finding["id"] not in ids
            ids.add(finding["id"])
            assert all(isinstance(finding[k], str) for k in ("id", "category", "priority", "chapter", "text", "reason", "source"))
            assert 0 <= finding["start"] <= finding["end"] <= len(finding["text"])
        temporal = next(f for f in report["findings"] if f["excerpt"] == "observa")
        assert temporal["rule"] == "coerencia_temporal"
        # Ações coordenadas do mesmo sujeito em tempos diferentes (sequência temporal, 1.3.1).
        assert temporal["relation"] == "coordinated_tense_mismatch"
        assert temporal["confidence"] == "alta"
        # A sugestão segue o aspecto da âncora: ‘abriu’ (perfeito) → ‘observou’.
        assert temporal["suggestion"] == "observou"
        anchor = temporal["related"][0]
        assert anchor["text"][anchor["start"]:anchor["end"]] == "abriu"
        manuscript = "\n".join(p.text for p in doc.paragraphs)
        assert manuscript[temporal["range"]["start"]:temporal["range"]["end"]] == "observa"
        assert sorted(p.name for p in output.iterdir()) == ["relatorio.json"]
        # A segunda execução não pode sobrescrever a saída da primeira.
        again = subprocess.run(result.args, cwd=ROOT / "fonte", capture_output=True, text=True, timeout=120)
        assert again.returncode != 0
        assert document.read_bytes() == original
        print(f"Contrato Python validado: {len(ids)} alertas, Unicode, caminhos especiais, hash e preservação dos arquivos.")

if __name__ == "__main__":
    main()
