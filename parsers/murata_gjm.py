from .base import LegacyScriptParser


class MurataGjmParser(LegacyScriptParser):
    maker = "murata"
    model = "GJM"
    script_name = "murata_GJM.py"
    input_folder = "murata_GJM"
    legacy_output_csv = "murata_GJM_output.csv"
