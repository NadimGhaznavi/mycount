"""Fitted model evidence and independent cohort decisions for one run."""

from dataclasses import dataclass

from mycount.entity.IsoForestObservation import IsoForestObservation


@dataclass(frozen=True)
class IsoForestResult:
    observations: tuple[IsoForestObservation, ...]
    decisions: tuple[float, ...]
    model: bytes | None
    manifest: dict[str, object]
