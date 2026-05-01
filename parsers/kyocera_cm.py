from .base import LegacyScriptParser


class KyoceraCmParser(LegacyScriptParser):
    maker = "kyocera"
    model = "CM"
    script_name = "kyocera_CM.py"
    input_folder = "kyocera_CM"
    legacy_output_csv = "kyocera_CM_output.csv"
