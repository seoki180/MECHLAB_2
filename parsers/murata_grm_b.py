from .base import LegacyScriptParser


class MurataGrmBParser(LegacyScriptParser):
    maker = "murata"
    model = "GRM(B)"
    script_name = "murata_GRM(B).py"
    input_folder = "murata_GRM(B)"
    legacy_output_csv = "murata_GRM(B)_output.csv"
