import re

line_start = r"^[+-][ ]*"
line_start_remove = r"^-[ ]*"
DEFAULT_LINE_SCORE = 1.0
# Stops looking after first match. Only searches a single line at a time.
change_patterns = [
    {"name": "description", "regex": re.compile(str(line_start + r"description")), "modifier": 0.0},
    {"name": "name", "regex": re.compile(str(line_start + r"name")), "modifier": 0.0},
    {"name": "comment", "regex": re.compile(str(line_start + r"!")), "modifier": 0.0},
    {"name": "dot1x", "regex": re.compile(str(line_start + r"dot1x")), "modifier": 0.5},
    {"name": "ntp", "regex": re.compile(str(line_start + r"ntp")), "modifier": 0.5},
    {"name": "snmp", "regex": re.compile(str(line_start + r"snmp")), "modifier": 0.5},
    {"name": "vrf", "regex": re.compile(str(line_start + r"vrf")), "modifier": 5.0},
    {"name": "removed ip address", "regex": re.compile(str(line_start_remove + r".*(ip address).*")), "modifier": 10.0},
    {"name": "removed vlan", "regex": re.compile(str(line_start_remove + r"vlan")), "modifier": 10.0},
    {"name": "spanning-tree mode", "regex": re.compile(str(line_start + r"spanning-tree mode")), "modifier": 50.0},
    {"name": "spanning-tree", "regex": re.compile(str(line_start + r"spanning-tree")), "modifier": 5.0},
    {
        "name": "removed routing",
        "regex": re.compile(str(line_start_remove + r".*(routing|router).*")),
        "modifier": 50.0,
    },
    {"name": "removed neighbor", "regex": re.compile(str(line_start_remove + r"neighbor")), "modifier": 10.0},
    {"name": "address-family", "regex": re.compile(str(line_start + r"address-family")), "modifier": 10.0},
    {"name": "redistribute", "regex": re.compile(str(line_start + r"redistribute")), "modifier": 10.0},
]
# TODO: multiline patterns / block-aware config


def calculate_line_score(line: str):
    for pattern in change_patterns:
        if re.match(pattern["regex"], line):
            return 1 * pattern["modifier"]
    return DEFAULT_LINE_SCORE


def calculate_score(config: str, diff: str) -> float:
    """
    Calculate a score based on how much and what configurations were changed in the diff.

    Args:
        config: the entire configuration of device after change
        diff: the diff of what changed in the configuration

    Returns:
        Calculated score, can be much higher than 100.0

    """
    config_lines = config.split("\n")
    diff_lines = diff.split("\n")
    changed_lines = 0
    total_line_score = 0.0
    for line in diff_lines:
        if line.startswith("+") or line.startswith("-"):
            changed_lines += 1
            total_line_score += calculate_line_score(line)

    changed_ratio = changed_lines / float(len(config_lines))
    unique_ratio = len(set(diff_lines)) / len(diff_lines)

    # Calculate score, 20% based on number of lines changed, 80% on individual
    # line score with applied modifiers
    # Apply uniqueness ratio to lower score if many lines are the same

    return ((changed_ratio * 100 * 0.2) + (total_line_score * 0.8)) * unique_ratio
