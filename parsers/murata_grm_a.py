from .base import LegacyScriptParser


class MurataGrmAParser(LegacyScriptParser):
    maker = "murata"
    model = "GRM(A)"
    script_name = "murata_GRM(A).py"
    input_folder = "murata_GRM(A)"
    legacy_output_csv = "murata_GRM(A)_output.csv"
