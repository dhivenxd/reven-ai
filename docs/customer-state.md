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


## 4. Revenue State

| Field | Type | Description |
|---|---|---|
| currency | string | Currency used for the customer's revenue |
| current_recurring_revenue | number | Current recurring revenue attributable to the customer |
| historical_revenue | number | Total revenue received from the customer before the decision date |
| last_payment_amount | number/null | Amount of the most recent successful payment |
| failed_payment_amount | number/null | Amount currently associated with the failed payment/revenue event |
| estimated_future_revenue | number | Estimated revenue the customer may generate over the chosen forecast horizon |
| estimated_customer_value | number | Estimated customer value based on historical and predicted future revenue |

### Derived fields

| Field | Description |
|---|---|
| revenue_at_risk | Revenue currently exposed to a payment failure, churn event, or other identified risk |
| revenue_risk_pct | Revenue at risk as a percentage of the customer's relevant revenue/value |
| forecast_horizon_days | Number of days used to estimate future revenue |
| net_revenue_opportunity | Estimated recoverable/retained revenue after expected intervention costs and incentives |

## 5. Engagement & Behavior

| Field | Type | Description |
|---|---|---|
| activity_count_30d | integer | Number of meaningful customer activities in the last 30 days |
| activity_count_previous_30d | integer | Number of meaningful activities in the preceding 30-day period |
| last_activity_date | date/null | Date of the customer's most recent meaningful activity |
| purchase_count_30d | integer | Number of purchases in the last 30 days |
| purchase_count_previous_30d | integer | Number of purchases in the preceding 30-day period |
| average_transaction_value | number | Average transaction value over the available history |
| support_interactions_30d | integer | Number of customer support interactions in the last 30 days |

### Derived fields

| Field | Description |
|---|---|
| activity_trend_pct | Percentage change in activity between the current and previous 30-day periods |
| purchase_trend_pct | Percentage change in purchase frequency between the current and previous 30-day periods |
| days_since_last_activity | Days since the most recent meaningful activity |
| engagement_risk | Derived indicator of declining customer engagement |

## 6. Churn & Risk

| Field | Type | Description |
|---|---|---|
| historical_churn_count | integer | Number of previous churn/cancellation events where applicable |
| previous_recovery_attempts | integer | Number of prior recovery attempts |
| previous_recovery_successes | integer | Number of prior recovery attempts that resulted in successful payment/revenue recovery |
| risk_event_type | enum/null | Current revenue-risk event being evaluated |
| risk_event_date | date/null | Date the current risk event occurred or was detected |

### Derived fields

| Field | Description |
|---|---|
| churn_probability | Model-estimated probability of churn within the defined forecast horizon |
| recovery_probability | Model-estimated probability of successful recovery under the relevant intervention |
| overall_revenue_risk_score | Combined score representing the customer's current revenue risk |
| prediction_confidence | Confidence/uncertainty associated with the model predictions |


## 7. Intervention History

| Field | Type | Description |
|---|---|---|
| total_interventions | integer | Total number of previous recovery/retention interventions |
| successful_interventions | integer | Number of previous interventions associated with successful recovery or retention |
| failed_interventions | integer | Number of previous interventions that did not achieve the intended outcome |
| last_intervention_type | enum/null | Type of the most recent intervention |
| last_intervention_date | date/null | Date of the most recent intervention |
| last_intervention_outcome | enum/null | Outcome of the most recent intervention |
| total_discount_given | number | Total value of discounts/incentives previously given |
| previous_actions | array | Historical intervention actions with dates and outcomes |


### Derived fields

| Field | Description |
|---|---|
| intervention_success_rate | Successful interventions divided by total interventions |
| days_since_last_intervention | Days since the most recent intervention |
| intervention_effectiveness_by_type | Historical effectiveness of each intervention type for this customer or segment |


## 8. Contact Fatigue & Customer Experience

| Field | Type | Description |
|---|---|---|
| contact_count_7d | integer | Number of customer-facing contacts in the last 7 days |
| contact_count_30d | integer | Number of customer-facing contacts in the last 30 days |
| retry_count_7d | integer | Number of payment retries attempted in the last 7 days |
| last_contact_date | date/null | Date of the most recent customer-facing contact |
| last_contact_channel | enum/null | Channel used for the most recent contact |
| last_customer_response | enum/null | Most recent observable response to an intervention |
| negative_response_count | integer | Number of previous negative responses to recovery/retention interventions |
| preferred_channel | enum/null | Known or inferred preferred communication channel, where available |

### Derived fields

| Field | Description |
|---|---|
| days_since_last_contact | Days since the most recent customer-facing contact |
| contact_fatigue_score | Derived score representing the likelihood that another contact creates excessive customer friction |
| intervention_pressure | Combined indicator of recent intervention intensity and customer response |
| contact_recommendation | Recommended contact level: proceed, limited, human review, or do not contact |
