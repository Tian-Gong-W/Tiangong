from tonmen.reasoning import MissionDirector

from .director_engine import MissionLoop as _DirectorMissionLoop
from .model import LoopStopReason, MissionLoopPolicy, MissionLoopResult


class MissionLoop(_DirectorMissionLoop):
    """Public Director-first loop with a runtime-bound capability authority."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.director = MissionDirector(self.runtime, reasoner=self.reasoner)
        self.reasoner = self.director.reasoner


__all__ = ["LoopStopReason", "MissionLoop", "MissionLoopPolicy", "MissionLoopResult"]
