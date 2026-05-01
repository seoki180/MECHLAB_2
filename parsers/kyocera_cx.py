from .base import LegacyScriptParser


class KyoceraCxParser(LegacyScriptParser):
    maker = "kyocera"
    model = "CX"
    script_name = "kyocera_CX.py"
    input_folder = "kyocera_CX"
    legacy_output_csv = "kyocera_cx_output.csv"
