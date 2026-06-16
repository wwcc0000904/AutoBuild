from __future__ import annotations

from rules.gain_rule import GainRule


class SatGainRule(GainRule):
    def __init__(self, values: list[str]) -> None:
        super().__init__("SatGain", values)
