
from datetime import datetime
from pathlib import Path
import pandas as pd


def save_report(report_text: str, output_dir: str | Path, prefix: str = "report") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{prefix}_{timestamp}.txt"
    # out_path.write_text(report_text, encoding="utf-8")
    return out_path


def save_csv(df: pd.DataFrame, output_dir: str | Path, prefix: str = "data") -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{prefix}_{timestamp}.csv"
    # df.to_csv(out_path, index=False)
    return out_path