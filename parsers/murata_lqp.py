from .base import LegacyScriptParser


class MurataLqpParser(LegacyScriptParser):
    maker = "murata"
    model = "LQP"
    script_name = "murata_LQP.py"
    input_folder = "murata_LQP"
    legacy_output_csv = "murata_LQP_output.csv"
