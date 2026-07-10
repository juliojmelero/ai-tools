from pathlib import Path

from research_documentation import DocumentationEngine

output_dir = Path("docs/generated/research_engine")
output_dir.mkdir(parents=True, exist_ok=True)

result = DocumentationEngine().generate(
    path="research_engine",
    language="python",
)

for index, artifact in enumerate(result.artifacts, start=1):
    extension = "puml" if artifact.renderer == "plantuml" else "txt"
    output_file = output_dir / (
        f"{index:02d}_{artifact.builder}_{artifact.renderer}.{extension}"
    )

    output_file.write_text(
        artifact.content,
        encoding="utf-8",
    )

    print(
        f"Generated: {output_file} "
        f"({len(artifact.content)} characters)"
    )
