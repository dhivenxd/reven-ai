from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationProfile:
    intervention: str
    raw_probability: float
    observed_probability: float
    calibration_factor: float


def build_calibration_profile(
    intervention: str,
    raw_probability: float,
    observed_probability: float,
) -> CalibrationProfile:

    if not 0.0 <= raw_probability <= 1.0:
        raise ValueError(
            "raw_probability must be between 0 and 1"
        )

    if not 0.0 <= observed_probability <= 1.0:
        raise ValueError(
            "observed_probability must be between 0 and 1"
        )

    if raw_probability == 0.0:
        calibration_factor = 1.0
    else:
        calibration_factor = (
            observed_probability
            / raw_probability
        )

    return CalibrationProfile(
        intervention=intervention,
        raw_probability=raw_probability,
        observed_probability=observed_probability,
        calibration_factor=calibration_factor,
    )


def calibrate_probability(
    raw_probability: float,
    profile: CalibrationProfile,
) -> float:

    calibrated_probability = (
        raw_probability
        * profile.calibration_factor
    )

    return max(
        0.0,
        min(calibrated_probability, 0.95),
    )


if __name__ == "__main__":

    profiles = [
        build_calibration_profile(
            intervention="payment_retry",
            raw_probability=0.6911,
            observed_probability=0.5524,
        ),
        build_calibration_profile(
            intervention="personalized_offer",
            raw_probability=0.5841,
            observed_probability=0.4878,
        ),
        build_calibration_profile(
            intervention="plan_change",
            raw_probability=0.6000,
            observed_probability=0.4533,
        ),
        build_calibration_profile(
            intervention="renewal_reminder",
            raw_probability=0.5500,
            observed_probability=0.4237,
        ),
    ]

    print("REVEN CALIBRATION MODEL")
    print("=" * 65)

    for profile in profiles:

        calibrated = calibrate_probability(
            profile.raw_probability,
            profile,
        )

        print("\n" + "-" * 65)

        print(
            f"Intervention: "
            f"{profile.intervention}"
        )

        print(
            f"Raw probability: "
            f"{profile.raw_probability:.2%}"
        )

        print(
            f"Observed probability: "
            f"{profile.observed_probability:.2%}"
        )

        print(
            f"Calibration factor: "
            f"{profile.calibration_factor:.4f}"
        )

        print(
            f"Calibrated probability: "
            f"{calibrated:.2%}"
        )