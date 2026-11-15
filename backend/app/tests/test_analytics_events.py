from app.services.analytics_events import analytics_metadata


def test_analytics_metadata_contains_only_buckets_and_categories():
    result = analytics_metadata(
        workspace_id=42, user_role="employee", surface="web_assistant", input_action="REDACT",
        trust_status="redacted", input_risk_score=0.81, output_risk_score=0.2,
        confidence=0.82, citation_count=3, model_called=True, latency_ms=2400,
        matches=[{"risk_category": "financial_data", "policy_name": "Payment cards", "rule_name": "PAN"}],
    )
    assert result == {
        "surface": "web_assistant", "decision": "redact", "input_risk_tier": "critical",
        "output_risk_tier": "low", "confidence_bucket": "0_75_to_0_89", "citation_count": 3,
        "response_time_bucket": "1_3s", "model_called": True, "workspace_id": "ws_42",
        "user_role": "employee", "trust_status": "redacted", "policy_categories": ["payment_card_data"],
    }
    assert result["policy_categories"] == ["payment_card_data"]
    assert "Payment cards" not in str(result) and "PAN" not in str(result)


def test_analytics_metadata_does_not_return_unknown_identity_or_policy_values():
    result = analytics_metadata(workspace_id=None, user_role="person@example.com", surface="web_assistant",
                                input_action=None, trust_status=None, matches=[{"risk_category": "unknown", "policy_name": "secret"}])
    assert "workspace_id" not in result and "user_role" not in result
    assert "secret" not in str(result)


def test_assistant_api_returns_safe_analytics_metadata(client, headers):
    prompt = "How long is parental leave? synthetic-private-sentinel"
    response = client.post("/api/assistant/chat", json={"message": prompt}, headers=headers["employee"])
    assert response.status_code == 200
    payload = response.json()
    assert payload["analytics"]["surface"] == "web_assistant"
    assert payload["analytics"]["user_role"] == "employee"
    assert payload["analytics"]["confidence_bucket"] in {"under_0_55", "0_55_to_0_74", "0_75_to_0_89", "0_90_plus", "unknown"}
    assert payload["analytics"]["response_time_bucket"] in {"under_1s", "1_3s", "3_10s", "10s_plus", "unknown"}
    assert prompt not in str(payload["analytics"])
    assert "message" not in payload["analytics"] and "policy_text" not in payload["analytics"]
