from app.agents.message_schema import AgentMessageSchema, Performative

def test_message_schema_has_required_protocol_fields():
    message = AgentMessageSchema(
        sender="BookingAPI",
        receiver="BookingAgent",
        performative=Performative.REQUEST,
        content={"action": "CREATE_BOOKING", "quantity": 2}
    )
    assert message.sender == "BookingAPI"
    assert message.receiver == "BookingAgent"
    assert message.performative == Performative.REQUEST
    assert message.content["quantity"] == 2
    assert message.conversation_id

def test_all_required_performatives_exist():
    assert {p.value for p in Performative} == {
        "REQUEST", "AGREE", "REFUSE", "PROPOSE", "INFORM", "FAILURE"
    }
