from __future__ import annotations

import pytest

from server.intents import UnknownIntent
from server.rule_interpreter import interpret_intent

EXPENSE_CASES = [
    ("$45 groceries", 45, "groceries", None, "groceries", None, []),
    ("45 groceries", 45, "groceries", None, "groceries", None, []),
    ("$12 coffee", 12, "coffee", None, None, None, []),
    ("$12.50 coffee", 12.5, "coffee", None, None, None, []),
    ("$1,250 rent", 1250, "rent", None, "rent", None, []),
    ("6/20 $200 car repair", 200, "car repair", None, "auto", None, []),
    ("$22 train", 22, "train", None, "transport", None, []),
    ("$50 karate class", 50, "karate class", None, "kids", None, []),
    ("$40 books", 40, "books", None, "kids", None, []),
    ("$200 flight deposit", 200, "flight deposit", None, "travel", None, []),
    ("$18 target", 18, "target", None, "shopping", None, []),
    ("$25 eating out", 25, "eating out", None, "eating out", None, []),
    ("$45 coffee, m: Fresh Street", 45, "coffee", "Fresh Street", None, None, []),
    ("$45 coffee, merchant: Corner Cafe", 45, "coffee", "Corner Cafe", None, None, []),
    ("$45 coffee, c: Groceries", 45, "coffee", None, "Groceries", None, []),
    ("$45 coffee, category: Dining Out", 45, "coffee", None, "Dining Out", None, []),
    ("$45 coffee, g: Healthy Lifestyle", 45, "coffee", None, None, "Healthy Lifestyle", []),
    ("$45 coffee, goal: Japan Trip", 45, "coffee", None, None, "Japan Trip", []),
    (
        "$45 coffee, m: Fresh Street, c: Groceries, g: Healthy Lifestyle",
        45,
        "coffee",
        "Fresh Street",
        "Groceries",
        "Healthy Lifestyle",
        [],
    ),
    ("$45 coffee, M: Fresh Street, C: Groceries", 45, "coffee", "Fresh Street", "Groceries", None, []),
    ("$12 coffee, one-off", 12, "coffee", None, None, None, ["one-off"]),
    ("$12 coffee, shared", 12, "coffee", None, None, None, ["shared"]),
    ("$12 coffee, reimbursable", 12, "coffee", None, None, None, ["reimbursable"]),
    (
        "$12 coffee, shared, reimbursable",
        12,
        "coffee",
        None,
        None,
        None,
        ["reimbursable", "shared"],
    ),
    ("$45 groceries, one-off", 45, "groceries", None, "groceries", None, ["one-off"]),
    ("$45 groceries, c: Dining Out", 45, "groceries", None, "Dining Out", None, []),
    ("$50 karate class, kid goal", 50, "karate class", None, "kids", "Raise a strong, resilient kid", []),
    ("$18 target, emergency fund goal", 18, "target", None, "shopping", "Emergency Fund", []),
    ("$40 books, learning goal", 40, "books", None, "kids", None, []),
    ("$200 flight deposit, family trip fund", 200, "flight deposit", None, "travel", None, []),
]


@pytest.mark.parametrize(
    ("raw_text", "amount", "description", "merchant", "category", "goal", "flags"),
    EXPENSE_CASES,
)
def test_expense_inputs_produce_log_contracts(
    raw_text,
    amount,
    description,
    merchant,
    category,
    goal,
    flags,
) -> None:
    intent = interpret_intent(raw_text)

    assert intent.intent == "log_expense"
    assert intent.amount == amount
    assert intent.description == description
    assert intent.merchant_reference == merchant
    assert intent.category_reference == category
    assert intent.goal_reference == goal
    assert intent.flags == flags


SET_BUDGET_CASES = [
    ("set groceries budget to $600", "groceries", 600, "current_cycle"),
    ("Set groceries budget to 600", "groceries", 600, "current_cycle"),
    ("set eating out budget to $200", "eating out", 200, "current_cycle"),
    ("set transport budget to $175.50", "transport", 175.5, "current_cycle"),
    ("change groceries budget to $450", "groceries", 450, "current_cycle"),
    ("change eating out budget to 0", "eating out", 0, "current_cycle"),
    ("set groceries budget to $500 this cycle", "groceries", 500, "current_cycle"),
    ("set groceries budget to $500 current cycle", "groceries", 500, "current_cycle"),
    ("set groceries budget to $500 next cycle", "groceries", 500, "next_cycle"),
    ("change transport budget to $190 next cycle", "transport", 190, "next_cycle"),
    ("set school supplies budget to $80", "school supplies", 80, "current_cycle"),
    ("set subscriptions budget to $25.", "subscriptions", 25, "current_cycle"),
]


@pytest.mark.parametrize(("raw_text", "category", "amount", "period"), SET_BUDGET_CASES)
def test_budget_updates_produce_write_contracts(raw_text, category, amount, period) -> None:
    intent = interpret_intent(raw_text)

    assert intent.intent == "set_budget"
    assert intent.category_reference == category
    assert intent.amount == amount
    assert intent.period.kind == period
    assert intent.requires_confirmation is True


@pytest.mark.parametrize(
    ("raw_text", "category"),
    [
        ("remove groceries budget", "groceries"),
        ("Remove groceries budget", "groceries"),
        ("remove the groceries budget", "groceries"),
        ("delete groceries budget", "groceries"),
        ("delete the transport budget", "transport"),
        ("remove eating out budget", "eating out"),
        ("remove subscriptions budget.", "subscriptions"),
        ("delete school supplies budget!", "school supplies"),
    ],
)
def test_budget_removals_produce_write_contracts(raw_text, category) -> None:
    intent = interpret_intent(raw_text)

    assert intent.intent == "remove_budget"
    assert intent.category_reference == category
    assert intent.requires_confirmation is True


@pytest.mark.parametrize(
    ("raw_text", "category"),
    [
        ("suggest a groceries budget", "groceries"),
        ("suggest groceries budget", "groceries"),
        ("Suggest a transport budget", "transport"),
        ("suggest an eating out budget", "eating out"),
        ("suggest a school supplies budget.", "school supplies"),
    ],
)
def test_budget_suggestions_produce_contracts(raw_text, category) -> None:
    intent = interpret_intent(raw_text)

    assert intent.intent == "suggest_budget"
    assert intent.category_reference == category


@pytest.mark.parametrize(
    ("raw_text", "report_type", "reference"),
    [
        ("report groceries", "category", "groceries"),
        ("Report groceries", "category", "groceries"),
        ("report eating out", "category", "eating out"),
        ("report transport", "category", "transport"),
        ("report subscriptions.", "category", "subscriptions"),
        ("report school supplies!", "category", "school supplies"),
        ("report goal resilient kid", "goal", "resilient kid"),
        ("Report goal Healthy Lifestyle", "goal", "Healthy Lifestyle"),
        ("report goal Japan Trip", "goal", "Japan Trip"),
        ("report goal Emergency Fund", "goal", "Emergency Fund"),
        ("report goal Save for family trip", "goal", "Save for family trip"),
        ("report goal Get promoted this year.", "goal", "Get promoted this year"),
    ],
)
def test_report_inputs_produce_contracts(raw_text, report_type, reference) -> None:
    intent = interpret_intent(raw_text)

    assert intent.intent == "report"
    assert intent.report_type == report_type
    assert intent.entity_reference == reference


QUERY_CASES = [
    ("how much on groceries this cycle?", "spent", "groceries", None, "current_cycle"),
    ("How much on transport?", "spent", "transport", None, "current_cycle"),
    ("how much did we spend on groceries?", "spent", "groceries", None, "current_cycle"),
    ("how much did I spend on eating out?", "spent", "eating out", None, "current_cycle"),
    ("how much have we spent on transport this cycle?", "spent", "transport", None, "current_cycle"),
    ("how much did we spend on groceries last cycle?", "spent", "groceries", None, "previous_cycle"),
    ("what's left in eating out?", "remaining", "eating out", None, "current_cycle"),
    ("what is left for groceries?", "remaining", "groceries", None, "current_cycle"),
    ("how much remains for transport?", "remaining", "transport", None, "current_cycle"),
    ("how much remains in groceries last cycle?", "remaining", "groceries", None, "previous_cycle"),
    ("how many expenses in groceries?", "expense_count", "groceries", None, "current_cycle"),
    ("how many purchases for eating out?", "expense_count", "eating out", None, "current_cycle"),
    ("what's the average expense in groceries?", "average", "groceries", None, "current_cycle"),
    ("what is the average for transport?", "average", "transport", None, "current_cycle"),
    ("what were the largest expenses in groceries?", "largest_expenses", "groceries", None, "current_cycle"),
    ("what are the largest expenses for eating out?", "largest_expenses", "eating out", None, "current_cycle"),
    ("what did we spend supporting the resilient kid goal this cycle?", "spent", None, "resilient kid", "current_cycle"),
    ("what did we put toward the healthy lifestyle goal this cycle?", "spent", None, "healthy lifestyle", "current_cycle"),
    ("how much did we spend this cycle?", "spent", None, None, "current_cycle"),
    ("how much have I spent last cycle?", "spent", None, None, "previous_cycle"),
]


@pytest.mark.parametrize(
    ("raw_text", "metric", "category", "goal", "period"),
    QUERY_CASES,
)
def test_questions_produce_query_contracts(raw_text, metric, category, goal, period) -> None:
    intent = interpret_intent(raw_text)

    assert intent.intent == "query_spending"
    assert intent.metric == metric
    assert intent.category_reference == category
    assert intent.goal_reference == goal
    assert intent.period.kind == period


CORRECTION_CASES = [
    ("oops, 54 not 45", 54, None, None, None),
    ("54 not 45", 54, None, None, None),
    ("oops 12.50 not 10", 12.5, None, None, None),
    ("no, that one's for the emergency fund goal", None, None, None, "emergency fund"),
    ("no, that one is for healthy lifestyle goal", None, None, None, "healthy lifestyle"),
    ("correct last expense, m: Corner Cafe", None, "Corner Cafe", None, None),
    ("update last expense, merchant: Fresh Street", None, "Fresh Street", None, None),
    ("correct the last expense, c: Dining Out", None, None, "Dining Out", None),
    ("update the last expense, category: Groceries", None, None, "Groceries", None),
    ("correct last expense, g: Japan Trip", None, None, None, "Japan Trip"),
]


@pytest.mark.parametrize(
    ("raw_text", "amount", "merchant", "category", "goal"),
    CORRECTION_CASES,
)
def test_corrections_produce_update_contracts(raw_text, amount, merchant, category, goal) -> None:
    intent = interpret_intent(raw_text)

    assert intent.intent == "correct_expense"
    assert intent.expense_reference == "last_expense"
    assert intent.amount == amount
    assert intent.merchant_reference == merchant
    assert intent.category_reference == category
    assert intent.goal_reference == goal


@pytest.mark.parametrize(
    "raw_text",
    [
        "hello",
        "coffee",
        "set a reminder",
        "transfer $100 to savings",
        "delete my account",
        "what should I cook?",
        "show me the weather",
        "pay my credit card",
    ],
)
def test_unsupported_inputs_produce_unknown_contracts(raw_text) -> None:
    intent = interpret_intent(raw_text)

    assert isinstance(intent, UnknownIntent)
    assert intent.confidence == 0


def test_ambiguous_goal_is_explicit_in_the_contract() -> None:
    intent = interpret_intent("$40 books, learning goal")

    assert intent.requires_confirmation is True
    assert intent.confidence == 0.75
    assert intent.ambiguities[0].field == "goal_reference"
    assert intent.ambiguities[0].candidates == [
        "Raise a strong, resilient kid",
        "Get promoted this year",
    ]


def test_history_is_a_client_session_intent() -> None:
    intent = interpret_intent("history")

    assert intent.intent == "show_history"
