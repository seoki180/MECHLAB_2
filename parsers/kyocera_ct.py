from .base import LegacyScriptParser


class KyoceraCtParser(LegacyScriptParser):
    maker = "kyocera"
    model = "CT"
    script_name = "kyocera_CT.py"
    input_folder = "kyocera_CT"
    legacy_output_csv = "kyocera_CT_output.csv"
