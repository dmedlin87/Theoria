from theo.services.api.app.ai.rag.models import RAGAnswer, RAGCitation


def test_rag_answer_model_dump_json_handles_guardrail_profile():
    answer = RAGAnswer(
        summary="example",
        citations=[
            RAGCitation(
                index=0,
                osis="Gen1:1",
                anchor="anchor",
                passage_id="pid",
                document_id="doc",
                snippet="snippet",
            )
        ],
    )

    json_payload = answer.model_dump_json()

    assert "\"guardrail_profile\":null" in json_payload
