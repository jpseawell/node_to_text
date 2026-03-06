# Node to Text

Node to Text is a Blender add-on for exporting a node graph into an LLM-friendly text format and importing the edited result back into Blender.

## Install in Blender

Do not use GitHub's green **Code > Download ZIP** button for Blender installation.

Instead:

1. Open the repository's **Releases** page.
2. Download the attached `node_to_text.zip` asset.
3. In Blender, open **Preferences > Add-ons > Install...**
4. Select `node_to_text.zip`.
5. Enable **Node to Text**.

## Create the Blender-ready zip locally

From the repository root:

```bash
python -m unittest discover -s tests -v
zip -qr node_to_text.zip node_to_text
```

## GitHub release automation

This repository includes a GitHub Actions workflow that:

- runs the test suite
- builds `node_to_text.zip`
- uploads the zip as a workflow artifact
- attaches the zip to published GitHub Releases
