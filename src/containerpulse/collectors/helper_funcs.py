import re

def parse_data_size(size_str):
    match = re.fullmatch(
        r"([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)\s*([a-zA-Z]+)",
        size_str.strip()
    )

    if not match:
        raise ValueError(f"Invalid data size format: '{size_str}'")

    value = float(match.group(1))
    unit = match.group(2)

    multipliers = {
        "B": 1,
        "kB": 1000,
        "KB": 1000,
        "MB": 1000 ** 2,
        "GB": 1000 ** 3,

        "KiB": 1024,
        "MiB": 1024 ** 2,
        "GiB": 1024 ** 3,
    }

    if unit not in multipliers:
        raise ValueError(f"Unknown data size unit: '{unit}'")

    return value * multipliers[unit]