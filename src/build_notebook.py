"""
Reconstruye el notebook .ipynb ejecutable a partir de un script de pipeline
plano (pipeline_republican.py o pipeline_democrat.py).

Ambos pipelines comparten la misma convención de marcado de celdas:

    # =====================================================================
    # CELDA "<título>" -- <nota de versión>
    # =====================================================================

Este script:
  1. Parte el pipeline en 6 celdas usando ese marcador.
  2. Antepone los imports correspondientes a cada celda (algunas celdas
     reimportan pandas/numpy porque en el notebook original cada celda de
     Jupyter se ejecuta en un kernel donde ya están cargados, pero el
     script plano se probó también como script standalone).
  3. Antepone una celda 0 (src/cell0_historical.py) que extrae los
     resultados históricos 2018/2022 desde los archivos de turnout.
  4. Escribe el .ipynb via nbformat (SIN ejecutar -- usar nbconvert
     --execute por separado, ver README.md).

Uso:
    python3 build_notebook.py --pipeline src/democrat/pipeline_democrat.py \
        --output notebooks/FLORIDA_2026_Primaria_Democrata_v8.ipynb

    python3 build_notebook.py --pipeline src/republican/pipeline_republican.py \
        --output notebooks/FLORIDA_2026_Primaria_Republicana_v7.ipynb

Luego, para ejecutar y verificar (0 errores/0 warnings esperado):
    jupyter nbconvert --to notebook --execute --output <mismo_archivo> \
        <mismo_archivo> --ExecutePreprocessor.timeout=180
(ejecutar con cwd = data/, o copiar los .xlsx de entrada al directorio de
ejecución -- el pipeline los lee por nombre de archivo relativo.)
"""
import argparse
import json
import re
from pathlib import Path

import nbformat as nbf

CELL_PATTERN = re.compile(
    r'# =+\n# CELDA "([^"]+)" -- [^\n]*\n# =+\n'
)

# Los imports se seleccionan por el NÚMERO de celda (prefijo "1.", "2.",
# ...) en vez del título exacto, porque el título del lado demócrata trae
# el sufijo "(Demócrata)" y el republicano no.
IMPORT_HEADERS_BY_CELL_NUMBER = {
    '1': "import pandas as pd\nimport numpy as np\nimport re\nfrom datetime import datetime\n\n",
    '2': "import pandas as pd\nimport numpy as np\n\n",
    '3': "import pandas as pd\nimport numpy as np\nimport scipy.stats as stats\n\n",
    '4': "import numpy as np\nimport pandas as pd\n\n",
    '5': "import numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\nimport seaborn as sns\n\n",
    '6': "import numpy as np\nimport pandas as pd\n\n",
}


def split_cells(pipeline_src):
    matches = list(CELL_PATTERN.finditer(pipeline_src))
    assert len(matches) == 6, f"Se esperaban 6 celdas, se encontraron {len(matches)}"
    cells = {}
    for i, m in enumerate(matches):
        title = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(pipeline_src)
        cells[title] = pipeline_src[start:end].strip('\n')
    return cells


def build(pipeline_path, cell0_path, output_path):
    pipeline_src = Path(pipeline_path).read_text(encoding='utf-8')
    cell0_src = Path(cell0_path).read_text(encoding='utf-8')

    raw_cells = split_cells(pipeline_src)

    final_cells = {}
    for title, code in raw_cells.items():
        cell_number = title.split('.', 1)[0].strip()
        header = IMPORT_HEADERS_BY_CELL_NUMBER.get(cell_number, "")
        final_cells[title] = header + code

    nb = nbf.v4.new_notebook()
    cells = [nbf.v4.new_code_cell(cell0_src)]
    for title, code in final_cells.items():
        cells.append(nbf.v4.new_markdown_cell(f"## {title}"))
        cells.append(nbf.v4.new_code_cell(code))
    cells.append(nbf.v4.new_markdown_cell(""))

    # Convención v1-v8: se omite el encabezado markdown de la celda
    # "5. Salidas, Dashboards y Alertas" (queda pegada visualmente a la
    # celda 4 en el notebook renderizado).
    cells = [
        c for c in cells
        if not (c['cell_type'] == 'markdown' and 'Salidas, Dashboards y Alertas' in ''.join(c['source']))
    ]
    nb['cells'] = cells

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

    print(f"OK -- {output_path} escrito con {len(nb['cells'])} celdas")
    for i, c in enumerate(nb['cells']):
        print(f"  {i}: {c['cell_type']:8s} {''.join(c['source'])[:70]!r}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--pipeline', required=True, help='Ruta al script de pipeline (.py)')
    parser.add_argument('--output', required=True, help='Ruta del .ipynb de salida')
    parser.add_argument('--cell0', default=None, help='Ruta a cell0_historical.py (default: src/cell0_historical.py)')
    args = parser.parse_args()

    cell0 = args.cell0 or str(Path(__file__).parent / 'cell0_historical.py')
    build(args.pipeline, cell0, args.output)
