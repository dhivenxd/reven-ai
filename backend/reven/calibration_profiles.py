from __future__ import annotations

from backend.reven.calibration_model import (
    CalibrationProfile,
    build_calibration_profile,
)
from backend.schemas.streamflix import InterventionType


def get_calibration_profiles() -> dict[InterventionType, CalibrationProfile]:
    """
    Synthetic calibration profiles used by the calibration experiment.

    Keys are InterventionType values so the decision engine can perform
    a type-safe lookup directly.
    """

    profiles = [
        (
            InterventionType.PAYMENT_RETRY,
            build_calibration_profile(
                intervention=InterventionType.PAYMENT_RETRY.value,
                raw_probability=0.6911,
                observed_probability=0.5524,
            ),
        ),
        (
            InterventionType.PERSONALIZED_OFFER,
            build_calibration_profile(
                intervention=InterventionType.PERSONALIZED_OFFER.value,
                raw_probability=0.5841,
                observed_probability=0.4878,
            ),
        ),
        (
            InterventionType.PLAN_CHANGE,
            build_calibration_profile(
                intervention=InterventionType.PLAN_CHANGE.value,
                raw_probability=0.6000,
                observed_probability=0.4533,
            ),
        ),
        (
            InterventionType.RENEWAL_REMINDER,
            build_calibration_profile(
                intervention=InterventionType.RENEWAL_REMINDER.value,
                raw_probability=0.5500,
                observed_probability=0.4237,
            ),
        ),
    ]

    return dict(profiles)


if __name__ == "__main__":
    profiles = get_calibration_profiles()

    print("REVEN CALIBRATION PROFILES")
    print("=" * 60)

    for action, profile in profiles.items():
        print()
        print("-" * 60)
        print(f"Intervention: {action.value}")
        print(f"Raw probability: {profile.raw_probability:.2%}")
        print(f"Observed probability: {profile.observed_probability:.2%}")
        print(f"Calibration factor: {profile.calibration_factor:.4f}")
