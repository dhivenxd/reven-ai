from dataclasses import dataclass, asdict
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class PaymentStatus(str, Enum):
    SUCCESSFUL = "successful"
    FAILED = "failed"
    PENDING = "pending"


class PaymentFailureReason(str, Enum):
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CARD_EXPIRED = "card_expired"
    BANK_DECLINED = "bank_declined"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_REQUIRED = "authentication_required"
    UNKNOWN = "unknown"


class EngagementTrend(str, Enum):
    INCREASING = "increasing"
    STABLE = "stable"
    DECLINING = "declining"
    UNKNOWN = "unknown"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskEventType(str, Enum):
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_RECOVERED = "payment_recovered"
    SUBSCRIPTION_EXPIRING = "subscription_expiring"
    CANCELLATION_REQUESTED = "cancellation_requested"
    CANCELLATION = "cancellation"
    ENGAGEMENT_DECLINE = "engagement_decline"
    INACTIVITY = "inactivity"
    RENEWAL_DUE = "renewal_due"


class InterventionType(str, Enum):
    PAYMENT_RETRY = "payment_retry"
    PAYMENT_REMINDER = "payment_reminder"
    RENEWAL_REMINDER = "renewal_reminder"
    PERSONALIZED_OFFER = "personalized_offer"
    DISCOUNT = "discount"
    PLAN_CHANGE = "plan_change"
    CANCELLATION_SAVE = "cancellation_save"
    NO_ACTION = "no_action"


class InterventionStatus(str, Enum):
    PROPOSED = "proposed"
    EXECUTED = "executed"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class Customer:
    customer_id: str
    signup_date: date
    tenure_days: int
    current_plan_id: str
    current_subscription_status: SubscriptionStatus
    lifetime_value: float
    created_at: datetime
    region: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")
        if self.tenure_days < 0:
            raise ValueError("tenure_days cannot be negative")
        if self.lifetime_value < 0:
            raise ValueError("lifetime_value cannot be negative")


@dataclass
class Subscription:
    subscription_id: str
    customer_id: str
    plan_id: str
    status: SubscriptionStatus
    start_date: date
    current_period_start: date
    current_period_end: date
    price: float
    currency: str
    auto_renew: bool
    cancellation_requested: bool = False
    cancelled_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.subscription_id:
            raise ValueError("subscription_id cannot be empty")
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")
        if self.price < 0:
            raise ValueError("price cannot be negative")
        if self.current_period_end < self.current_period_start:
            raise ValueError("subscription period end cannot precede start")


@dataclass
class Payment:
    payment_id: str
    customer_id: str
    subscription_id: str
    amount: float
    currency: str
    payment_method: str
    status: PaymentStatus
    attempted_at: datetime
    failure_reason: Optional[PaymentFailureReason] = None
    retry_count: int = 0

    def __post_init__(self) -> None:
        if not self.payment_id:
            raise ValueError("payment_id cannot be empty")
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")
        if self.amount < 0:
            raise ValueError("amount cannot be negative")
        if self.retry_count < 0:
            raise ValueError("retry_count cannot be negative")


@dataclass
class EngagementSnapshot:
    customer_id: str
    observation_date: date
    active_days: int
    total_watch_minutes: float
    average_daily_watch_minutes: float
    unique_content_count: int
    engagement_score: float
    engagement_trend: EngagementTrend

    def __post_init__(self) -> None:
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")
        if self.active_days < 0:
            raise ValueError("active_days cannot be negative")
        if self.total_watch_minutes < 0:
            raise ValueError("total_watch_minutes cannot be negative")
        if self.average_daily_watch_minutes < 0:
            raise ValueError("average_daily_watch_minutes cannot be negative")
        if self.unique_content_count < 0:
            raise ValueError("unique_content_count cannot be negative")


@dataclass
class RiskEvent:
    event_id: str
    customer_id: str
    event_type: RiskEventType
    occurred_at: datetime
    severity: RiskSeverity
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id cannot be empty")
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")


@dataclass
class Intervention:
    intervention_id: str
    customer_id: str
    intervention_type: InterventionType
    created_at: datetime
    channel: str
    cost: float
    reason: str
    status: InterventionStatus
    offer_value: float = 0.0

    def __post_init__(self) -> None:
        if not self.intervention_id:
            raise ValueError("intervention_id cannot be empty")
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")
        if self.cost < 0:
            raise ValueError("cost cannot be negative")
        if self.offer_value < 0:
            raise ValueError("offer_value cannot be negative")


@dataclass
class Outcome:
    outcome_id: str
    customer_id: str
    evaluated_at: datetime
    subscription_renewed: bool
    payment_recovered: bool
    churned: bool
    revenue_preserved: float
    intervention_cost: float
    net_revenue: float
    reason: str
    intervention_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.outcome_id:
            raise ValueError("outcome_id cannot be empty")
        if not self.customer_id:
            raise ValueError("customer_id cannot be empty")
        if self.revenue_preserved < 0:
            raise ValueError("revenue_preserved cannot be negative")
        if self.intervention_cost < 0:
            raise ValueError("intervention_cost cannot be negative")


def to_dict(obj: Any) -> dict[str, Any]:
    """Convert a schema object into a serializable dictionary."""
    return asdict(obj)


if __name__ == "__main__":
    now = datetime.now()
    today = now.date()

    customer = Customer(
        customer_id="cust_001",
        signup_date=today,
        tenure_days=120,
        current_plan_id="standard",
        current_subscription_status=SubscriptionStatus.ACTIVE,
        lifetime_value=1999.0,
        created_at=now,
    )

    subscription = Subscription(
        subscription_id="sub_001",
        customer_id="cust_001",
        plan_id="standard",
        status=SubscriptionStatus.ACTIVE,
        start_date=today,
        current_period_start=today,
        current_period_end=today,
        price=399.0,
        currency="INR",
        auto_renew=True,
    )

    payment = Payment(
        payment_id="pay_001",
        customer_id="cust_001",
        subscription_id="sub_001",
        amount=399.0,
        currency="INR",
        payment_method="card",
        status=PaymentStatus.SUCCESSFUL,
        attempted_at=now,
    )

    engagement = EngagementSnapshot(
        customer_id="cust_001",
        observation_date=today,
        active_days=18,
        total_watch_minutes=1800.0,
        average_daily_watch_minutes=100.0,
        unique_content_count=24,
        engagement_score=0.78,
        engagement_trend=EngagementTrend.STABLE,
    )

    risk_event = RiskEvent(
        event_id="risk_001",
        customer_id="cust_001",
        event_type=RiskEventType.RENEWAL_DUE,
        occurred_at=now,
        severity=RiskSeverity.MEDIUM,
        metadata={},
    )

    intervention = Intervention(
        intervention_id="int_001",
        customer_id="cust_001",
        intervention_type=InterventionType.PAYMENT_RETRY,
        created_at=now,
        channel="in_app",
        cost=2.0,
        reason="Payment recovery",
        status=InterventionStatus.EXECUTED,
    )

    outcome = Outcome(
        outcome_id="out_001",
        customer_id="cust_001",
        intervention_id="int_001",
        evaluated_at=now,
        subscription_renewed=True,
        payment_recovered=True,
        churned=False,
        revenue_preserved=399.0,
        intervention_cost=2.0,
        net_revenue=397.0,
        reason="Payment recovered successfully",
    )

    for item in (
        customer,
        subscription,
        payment,
        engagement,
        risk_event,
        intervention,
        outcome,
    ):
        print(to_dict(item))