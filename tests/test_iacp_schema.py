from obsidian_orchestration.schemas.iacp import (
    AgentName,
    IACPMessage,
    Performative,
    TaskEnvelope,
    TaskType,
)


def test_message_roundtrip():
    task = TaskEnvelope(type=TaskType.SCOUT, objective="Find MCP docs")
    msg = IACPMessage(
        from_agent=AgentName.PRIMARY,
        to_agent=AgentName.RESEARCH_SCOUT,
        performative=Performative.REQUEST,
        task=task,
        confidence=0.9,
        rationale="Need sources",
        expected_output="Scout Report",
    )
    assert msg.protocol == "IACP/1.0"
    reply = msg.reply(
        from_agent=AgentName.RESEARCH_SCOUT,
        performative=Performative.INFORM,
        payload={"report": "ok"},
        confidence=0.7,
        rationale="done",
    )
    assert reply.in_reply_to == msg.message_id
    assert reply.conversation_id == msg.conversation_id
    assert reply.to_agent == AgentName.PRIMARY
