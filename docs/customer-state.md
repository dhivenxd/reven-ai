# REVEN Customer State

## 1. Customer Identity

| Field | Type | Description |
|---|---|---|
| customer_id | string | Unique customer identifier |
| signup_date | date | Date the customer relationship began |
| country | string | Customer country/market |

### Derived fields

| Field | Description |
|---|---|
tenure_months | Derived number of months between signup_date and the decision date
| customer_segment | Derived from customer value/behavior; not manually provided |

## 2. Subscription State

| Field | Type | Description |
|---|---|---|
| subscription_id | string | Unique subscription identifier |
| plan_id | string | Identifier for the current plan |
| monthly_price | number | Current recurring price |
| billing_interval | enum | Billing frequency (monthly, yearly, etc.) |
| subscription_start_date | date | Date the subscription began |
| next_billing_date | date | Next scheduled billing/renewal date |
| current_status | enum | Current subscription status |
| previous_plan_id | string/null | Previous plan, if a plan change occurred |
| previous_price | number/null | Previous recurring price, if changed |

### Derived fields

| Field | Description |
|---|---|
| days_to_renewal | Days between decision date and next billing date |
| price_change_pct | Percentage change from previous price to current price |

## 3. Payment State

| Field | Type | Description |
|---|---|---|
| payment_method_type | enum | Card, UPI, bank transfer, wallet, etc. |
| payment_method_age_days | integer | Age of the current payment method |
| payment_status | enum | Success, failed, pending, refunded, etc. |
| last_failure_reason | enum/null | Reason for the most recent payment failure |
| failure_count_30d | integer | Number of payment failures in the last 30 days |
| failure_count_total | integer | Total historical payment failures |
| successful_payment_count | integer | Total successful payments |
| last_successful_payment_date | date/null | Date of most recent successful payment |
| last_payment_attempt_date | date/null | Date of most recent payment attempt |
| payment_method_expiry_date | date/null | Expiry date where applicable |

### Derived fields

| Field | Description |
|---|---|
| payment_success_rate | Successful payments divided by total payment attempts |
| days_since_last_success | Days since the most recent successful payment |
| days_since_last_failure | Days since the most recent failed payment |
| payment_failure_trend | Whether payment failures are increasing, stable, or decreasing |
| payment_method_expiry_risk | Risk that the payment method will expire before the next billing event |
