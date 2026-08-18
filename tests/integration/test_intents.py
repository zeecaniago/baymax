from __future__ import annotations

import pytest

from server.entity_resolution import resolve_category, resolve_goal, resolve_merchant

from .helpers import category_from, create_expense

pytestmark = pytest.mark.integration


def test_interpret_endpoint_exposes_the_shared_contract(client) -> None:
    response = client.post(
        "/intents/interpret",
        json={"raw_text": "$45 coffee, m: Fresh Street, c: Groceries"},
    )

    assert response.status_code == 200
    intent = response.json()
    assert intent["schema_version"] == "1.0"
    assert intent["source"] == "rules"
    assert intent["intent"] == "log_expense"
    assert intent["amount"] == 45
    assert intent["merchant_reference"] == "Fresh Street"
    assert intent["category_reference"] == "Groceries"


def test_entity_resolution_is_exact_partial_ambiguous_and_non_inventive(client) -> None:
    create_expense(client, merchant="Fresh Street")

    category = resolve_category("GROCERIES")
    merchant = resolve_merchant("fresh")
    goal = resolve_goal("resilient kid")
    ambiguous_goal = resolve_goal("trip")
    missing_goal = resolve_goal("retire on mars")

    assert (category.status, category.canonical_name) == ("resolved", "groceries")
    assert (merchant.status, merchant.canonical_name) == ("resolved", "Fresh Street")
    assert (goal.status, goal.entity_id) == ("resolved", "goal-resilient-kid")
    assert ambiguous_goal.status == "ambiguous"
    assert {candidate.entity_id for candidate in ambiguous_goal.candidates} == {
        "goal-family-trip",
        "goal-japan-trip",
    }
    assert missing_goal.status == "not_found"


def test_log_intent_executes_through_persistence_and_reports(client) -> None:
    interpreted = client.post(
        "/intents/interpret",
        json={"raw_text": "$45 coffee, m: Fresh Street, c: Groceries"},
    ).json()

    executed = client.post(
        "/intents/execute",
        json={"intent": interpreted},
    )

    assert executed.status_code == 200
    result = executed.json()
    assert result["status"] == "executed"
    assert result["data"]["expense"]["merchant"] == "Fresh Street"
    assert category_from(client.get("/reports"))["spent"] == 45


def test_ambiguous_intent_requests_clarification_without_writing(client) -> None:
    intent = client.post(
        "/intents/interpret",
        json={"raw_text": "$40 books, learning goal"},
    ).json()

    result = client.post("/intents/execute", json={"intent": intent}).json()

    assert result["status"] == "clarification_required"
    assert "Which goal" in result["message"]
    assert client.get("/expenses").json()["count"] == 0


def test_write_intent_requires_confirmation_before_mutating(client) -> None:
    intent = client.post(
        "/intents/interpret",
        json={"raw_text": "set groceries budget to $600"},
    ).json()

    pending = client.post("/intents/execute", json={"intent": intent}).json()
    before = category_from(client.get("/budgets"))
    executed = client.post(
        "/intents/execute",
        json={"intent": intent, "confirmed": True},
    ).json()
    after = category_from(client.get("/budgets"))

    assert pending["status"] == "confirmation_required"
    assert before["budget_amount"] == 400
    assert executed["status"] == "executed"
    assert after["budget_amount"] == 600


def test_correction_intent_uses_the_explicit_last_expense_context(client) -> None:
    expense = create_expense(client)
    intent = client.post(
        "/intents/interpret",
        json={"raw_text": "oops, 54 not 45"},
    ).json()

    result = client.post(
        "/intents/execute",
        json={"intent": intent, "last_expense_id": expense["id"]},
    ).json()

    assert result["status"] == "executed"
    assert result["data"]["expense"]["amount"] == 54
    assert category_from(client.get("/reports"))["spent"] == 54


def test_paraphrased_question_is_interpreted_then_calculated(client) -> None:
    create_expense(client, amount=45)

    response = client.post(
        "/ask",
        json={"question": "how much did we spend on groceries?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == (
        "Groceries: $45.00 of $400.00 (11%) — 1 expenses"
    )


def test_missing_question_entity_returns_clarification_not_unrelated_totals(client) -> None:
    response = client.post(
        "/ask",
        json={"question": "how much did we spend on moon cheese?"},
    )

    assert response.status_code == 200
    assert response.json()["answer"] == "No category matches 'moon cheese'."
    assert response.json()["supporting_data"]["intent_status"] == (
        "clarification_required"
    )


def test_future_cycle_budget_is_not_silently_applied_to_current_cycle(client) -> None:
    intent = client.post(
        "/intents/interpret",
        json={"raw_text": "set groceries budget to $600 next cycle"},
    ).json()

    result = client.post(
        "/intents/execute",
        json={"intent": intent, "confirmed": True},
    ).json()

    assert result["status"] == "unsupported"
    assert category_from(client.get("/budgets"))["budget_amount"] == 400


def test_remove_budget_and_report_intents_use_existing_domain_data(client) -> None:
    create_expense(client, amount=75)
    report_intent = client.post(
        "/intents/interpret",
        json={"raw_text": "report groceries"},
    ).json()

    report_result = client.post(
        "/intents/execute",
        json={"intent": report_intent},
    ).json()
    remove_intent = client.post(
        "/intents/interpret",
        json={"raw_text": "remove groceries budget"},
    ).json()
    remove_result = client.post(
        "/intents/execute",
        json={"intent": remove_intent, "confirmed": True},
    ).json()

    assert report_result["status"] == "executed"
    assert report_result["data"]["report"]["spent"] == 75
    assert remove_result["status"] == "executed"
    assert category_from(client.get("/budgets"))["budget_amount"] is None


@pytest.mark.parametrize("raw_text", ["hello", "history", "suggest a groceries budget"])
def test_non_server_contracts_return_explicit_unsupported_results(client, raw_text) -> None:
    intent = client.post(
        "/intents/interpret",
        json={"raw_text": raw_text},
    ).json()

    result = client.post("/intents/execute", json={"intent": intent}).json()

    assert result["status"] == "unsupported"
