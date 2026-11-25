"""
Unit tests for the batch jobs of structured JSON calls: the provider interface,
the Mistral batch API (mocked HTTP) and the AIService layer.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic import BaseModel, Field

from lys.apps.ai.modules.core.services import AIService
from lys.apps.ai.utils.providers import AnthropicProvider, MistralProvider
from lys.apps.ai.utils.providers.abstracts import AIBatchJob, AIBatchRequest, AIBatchResult, AIBatchState
from lys.apps.ai.utils.providers.config import AIEndpointConfig
from lys.apps.ai.utils.providers.exceptions import (
    AIProviderError,
    AIRateLimitError,
    AIResponseTruncatedError,
    AITimeoutError,
    AIValidationError,
)


class Answer(BaseModel):
    label: str


class ShortAnswer(BaseModel):
    label: str = Field(json_schema_extra={"maxLength": 5})


@pytest.fixture
def provider():
    return MistralProvider()


@pytest.fixture
def config():
    return AIEndpointConfig(provider="mistral", model="mistral-medium-2604", api_key="test-api-key",
                            timeout=30, system_prompt="Classify.", options={"temperature": 0, "unknown": 1})


def _requests(count=2):
    return [AIBatchRequest(custom_id=f"r{index}", messages=[{"role": "user", "content": f"Text {index}"}])
            for index in range(count)]


def _response(status_code=200, payload=None, text=""):
    response = MagicMock(spec=httpx.Response)
    response.headers = httpx.Headers()
    response.status_code = status_code
    response.json.return_value = payload or {}
    response.text = text
    return response


def _job(status="QUEUED", **extra):
    return {"id": "9696e6ca-f4e2-46d5-883e-b80305bad24e", "status": status, "model": "mistral-medium-2604",
            "total_requests": "2", "succeeded_requests": "1", "failed_requests": "0", **extra}


def _record(custom_id, content, status_code=200, finish_reason="stop"):
    """A result record as the API returns it (measured 2026-11-21)."""
    return {"id": f"batch-{custom_id}", "custom_id": custom_id, "response": {"status_code": status_code, "body": {
        "object": "chat.completion", "model": "mistral-medium-2604",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                     "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 21, "completion_tokens": 2, "total_tokens": 23},
    }}}


def _sync_client(*responses, method="get"):
    client = MagicMock()
    getattr(client, method).side_effect = list(responses)
    patcher = patch("httpx.Client")
    mocked = patcher.start()
    mocked.return_value.__enter__.return_value = client
    return patcher, client


def _async_client(*responses, method="get"):
    client = AsyncMock()
    getattr(client, method).side_effect = list(responses)
    patcher = patch("httpx.AsyncClient")
    mocked = patcher.start()
    mocked.return_value.__aenter__.return_value = client
    return patcher, client


class TestBatchState:

    def test_only_a_pending_job_is_not_final(self):
        assert not AIBatchState.PENDING.is_final
        assert all(state.is_final for state in AIBatchState if state is not AIBatchState.PENDING)


class TestOptionalCapability:

    def test_a_provider_without_batch_jobs_says_so(self, config):
        with pytest.raises(NotImplementedError):
            AnthropicProvider().submit_json_batch_sync(_requests(), config, Answer)
        with pytest.raises(NotImplementedError):
            AnthropicProvider().get_json_batch_results_sync("job", config, Answer)


class TestMistralBatchPayload:

    @staticmethod
    def _lines(content: bytes) -> list[dict]:
        return [json.loads(line) for line in content.decode("utf-8").splitlines()]

    def test_each_request_is_one_line_with_the_body_chat_json_sends(self, provider, config):
        messages = [{"role": "system", "content": "Classify."}, {"role": "user", "content": "Texte é"}]

        [line] = self._lines(provider._batch_file([AIBatchRequest("r0", messages)], config, Answer))

        expected = provider._json_payload(messages, config, Answer)
        expected.pop("model")
        assert line == {"custom_id": "r0", "body": expected}
        assert line["body"]["response_format"]["json_schema"]["strict"] is True
        assert line["body"]["temperature"] == 0 and "unknown" not in line["body"]

    def test_the_job_is_created_on_the_file_with_the_model_set_once(self, provider, config):
        payload = provider._batch_job_payload("file-in", config, {"origin": "test"}, 12)

        assert payload == {"model": "mistral-medium-2604", "endpoint": "/v1/chat/completions",
                           "input_files": ["file-in"], "metadata": {"origin": "test"}, "timeout_hours": 12}

    def test_no_metadata_nor_timeout_leaves_the_provider_s_defaults(self, provider, config):
        payload = provider._batch_job_payload("file-in", config, None, None)

        assert "metadata" not in payload and "timeout_hours" not in payload

    @pytest.mark.parametrize("requests", [
        [],
        [AIBatchRequest("same", []), AIBatchRequest("same", [])],
    ])
    def test_an_empty_job_or_a_repeated_id_is_refused(self, provider, config, requests):
        with pytest.raises(ValueError):
            provider._batch_file(requests, config, Answer)

    def test_more_requests_than_one_job_takes_are_refused(self, provider, config, monkeypatch):
        monkeypatch.setattr(MistralProvider, "MAX_BATCH_REQUESTS", 2)

        with pytest.raises(ValueError):
            provider._batch_file(_requests(3), config, Answer)

    def test_an_input_file_larger_than_one_job_takes_is_refused(self, provider, config, monkeypatch):
        one_line = len(provider._batch_file(_requests(1), config, Answer))
        monkeypatch.setattr(MistralProvider, "MAX_BATCH_FILE_BYTES", one_line + 1)

        with pytest.raises(ValueError, match="request 2 of 3"):
            provider._batch_file(_requests(3), config, Answer)

    def test_an_input_file_at_the_bound_is_accepted(self, provider, config, monkeypatch):
        content = provider._batch_file(_requests(2), config, Answer)
        monkeypatch.setattr(MistralProvider, "MAX_BATCH_FILE_BYTES", len(content))

        assert provider._batch_file(_requests(2), config, Answer) == content

    @pytest.mark.parametrize("job_id", ["../files", "abc/cancel", "a b", ""])
    def test_an_id_that_could_reach_another_endpoint_is_refused_before_any_call(self, provider, config, job_id):
        with patch("httpx.Client") as client:
            with pytest.raises(ValueError):
                provider.get_batch_sync(job_id, config)
        client.assert_not_called()


class TestMistralBatchJob:

    def test_a_job_is_submitted_on_its_uploaded_file_and_read_in_neutral_terms(self, provider, config):
        patcher, client = _sync_client(_response(payload={"id": "file-in", "purpose": "batch"}),
                                       _response(payload=_job("QUEUED")), method="post")
        try:
            job = provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        upload, create = client.post.call_args_list
        assert upload.args[0] == "https://api.mistral.ai/v1/files" and upload.kwargs["data"] == {"purpose": "batch"}
        name, content, content_type = upload.kwargs["files"]["file"]
        assert (name, content_type) == ("batch.jsonl", "application/jsonl")
        assert content == provider._batch_file(_requests(), config, Answer)
        assert "Content-Type" not in upload.kwargs["headers"]
        assert create.args[0] == "https://api.mistral.ai/v1/batch/jobs"
        assert create.kwargs["json"]["input_files"] == ["file-in"]
        assert job == AIBatchJob(id="9696e6ca-f4e2-46d5-883e-b80305bad24e", state=AIBatchState.PENDING,
                                 provider="mistral", model="mistral-medium-2604", total_requests=2,
                                 succeeded_requests=1, failed_requests=0)

    @pytest.mark.parametrize("status, state", [
        ("RUNNING", AIBatchState.PENDING),
        ("CANCELLATION_REQUESTED", AIBatchState.PENDING),
        ("SUCCESS", AIBatchState.COMPLETED),
        ("FAILED", AIBatchState.FAILED),
        ("TIMEOUT_EXCEEDED", AIBatchState.EXPIRED),
        ("CANCELLED", AIBatchState.CANCELLED),
    ])
    def test_each_status_has_its_state(self, provider, config, status, state):
        patcher, _ = _sync_client(_response(payload=_job(status)))
        try:
            assert provider.get_batch_sync("job-1", config).state is state
        finally:
            patcher.stop()

    def test_a_status_not_known_is_an_error_never_a_guess(self, provider, config):
        patcher, _ = _sync_client(_response(payload=_job("PAUSED")))
        try:
            with pytest.raises(AIProviderError):
                provider.get_batch_sync("job-1", config)
        finally:
            patcher.stop()

    def test_a_refused_job_raises_its_error_and_deletes_its_input_file(self, provider, config):
        patcher, client = _sync_client(_response(payload={"id": "file-in"}), _response(status_code=429),
                                       method="post")
        client.delete.return_value = _response(payload={"id": "file-in", "deleted": True})
        try:
            with pytest.raises(AIRateLimitError):
                provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        assert client.delete.call_args.args[0] == "https://api.mistral.ai/v1/files/file-in"

    def test_a_failed_deletion_is_logged_and_the_job_s_error_raised(self, provider, config, caplog):
        patcher, client = _sync_client(_response(payload={"id": "file-in"}), _response(status_code=500),
                                       method="post")
        client.delete.side_effect = httpx.ConnectError("down")
        try:
            with pytest.raises(AIProviderError, match="server error"):
                provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        assert "file-in not deleted: ConnectError" in caplog.text

    def test_a_deletion_refused_is_logged(self, provider, config, caplog):
        patcher, client = _sync_client(_response(payload={"id": "file-in"}), _response(status_code=429),
                                       method="post")
        client.delete.return_value = _response(status_code=500)
        try:
            with pytest.raises(AIRateLimitError):
                provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        assert "file-in not deleted: HTTP 500" in caplog.text

    def test_after_a_timeout_the_input_file_is_kept(self, provider, config):
        # The job may have been created on it: deleting the file could break that job.
        patcher, client = _sync_client(_response(payload={"id": "file-in"}), httpx.TimeoutException("slow"),
                                       method="post")
        try:
            with pytest.raises(AITimeoutError):
                provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        client.delete.assert_not_called()

    def test_an_accepted_job_keeps_its_input_file(self, provider, config):
        patcher, client = _sync_client(_response(payload={"id": "file-in"}), _response(payload=_job("QUEUED")),
                                       method="post")
        try:
            provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        client.delete.assert_not_called()

    def test_a_refused_upload_creates_no_job(self, provider, config):
        patcher, client = _sync_client(_response(status_code=400, text="too large"), method="post")
        try:
            with pytest.raises(AIProviderError):
                provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        assert client.post.call_count == 1

    @pytest.mark.parametrize("upload", [{}, {"id": "../batch/jobs"}, {"id": 12}])
    def test_an_upload_answer_without_a_valid_id_is_a_provider_error(self, provider, config, upload):
        patcher, client = _sync_client(_response(payload=upload), method="post")
        try:
            with pytest.raises(AIProviderError):
                provider.submit_json_batch_sync(_requests(), config, Answer)
        finally:
            patcher.stop()

        assert client.post.call_count == 1

    def test_a_job_is_cancelled_on_its_own_url(self, provider, config):
        patcher, client = _sync_client(_response(payload=_job("CANCELLATION_REQUESTED")), method="post")
        try:
            job = provider.cancel_batch_sync("job-1", config)
        finally:
            patcher.stop()

        assert client.post.call_args.args[0] == "https://api.mistral.ai/v1/batch/jobs/job-1/cancel"
        assert job.state is AIBatchState.PENDING

    @pytest.mark.asyncio
    async def test_the_async_twin_submits_the_same_job(self, provider, config):
        patcher, client = _async_client(_response(payload={"id": "file-in"}), _response(payload=_job("QUEUED")),
                                        method="post")
        try:
            job = await provider.submit_json_batch(_requests(), config, Answer)
        finally:
            patcher.stop()

        upload, create = client.post.call_args_list
        assert upload.kwargs["files"]["file"][1] == provider._batch_file(_requests(), config, Answer)
        assert create.kwargs["json"] == provider._batch_job_payload("file-in", config, None, None)
        assert job.state is AIBatchState.PENDING

    @pytest.mark.asyncio
    async def test_the_async_twin_deletes_the_input_file_of_a_refused_job(self, provider, config):
        patcher, client = _async_client(_response(payload={"id": "file-in"}), _response(status_code=429),
                                        method="post")
        client.delete.return_value = _response(payload={"id": "file-in", "deleted": True})
        try:
            with pytest.raises(AIRateLimitError):
                await provider.submit_json_batch(_requests(), config, Answer)
        finally:
            patcher.stop()

        client.delete.assert_awaited_once()
        assert client.delete.call_args.args[0] == "https://api.mistral.ai/v1/files/file-in"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("delete, logged", [
        ({"side_effect": httpx.ConnectError("down")}, "ConnectError"),
        ({"return_value": _response(status_code=500)}, "HTTP 500"),
    ])
    async def test_the_async_twin_logs_a_failed_deletion(self, provider, config, caplog, delete, logged):
        patcher, client = _async_client(_response(payload={"id": "file-in"}), _response(status_code=429),
                                        method="post")
        client.delete.configure_mock(**delete)
        try:
            with pytest.raises(AIRateLimitError):
                await provider.submit_json_batch(_requests(), config, Answer)
        finally:
            patcher.stop()

        assert f"file-in not deleted: {logged}" in caplog.text


class TestMistralBatchResults:

    def _results(self, provider, config, job, *files, schema=Answer):
        # A job with no result file is read again inline.
        reads = [_response(payload=job)] * (1 if job.get("output_file") or job.get("error_file") else 2)
        patcher, client = _sync_client(*reads, *[_response(text=content) for content in files])
        try:
            return provider.get_json_batch_results_sync("job-1", config, schema), client
        finally:
            patcher.stop()

    def test_without_result_files_the_inline_results_are_validated_like_a_direct_answer(self, provider, config):
        job = _job("SUCCESS", outputs=[_record("r0", '{"label": "ok"}')])

        results, client = self._results(provider, config, job)

        assert "params" not in client.get.call_args_list[0].kwargs
        assert client.get.call_args_list[1].kwargs["params"] == {"inline": "true"}
        assert results == [AIBatchResult(custom_id="r0", data=Answer(label="ok"),
                                         usage={"prompt_tokens": 21, "completion_tokens": 2, "total_tokens": 23})]

    def test_a_failed_request_carries_the_error_of_its_status(self, provider, config):
        job = _job("SUCCESS", outputs=[_record("r0", "", status_code=429)])

        [result], _ = self._results(provider, config, job)

        assert result.data is None and isinstance(result.error, AIRateLimitError) and "r0" in str(result.error)

    def test_an_answer_off_its_schema_is_a_validation_error(self, provider, config):
        job = _job("SUCCESS", outputs=[_record("r0", '{"other": 1}')])

        [result], _ = self._results(provider, config, job)

        assert type(result.error) is AIValidationError and result.data is None

    def test_an_answer_cut_by_the_output_limit_is_a_truncation(self, provider, config):
        job = _job("SUCCESS", outputs=[_record("r0", '{"label": "o', finish_reason="length")])

        [result], _ = self._results(provider, config, job)

        assert isinstance(result.error, AIResponseTruncatedError)

    def test_a_record_naming_no_request_is_left_out(self, provider, config):
        job = _job("SUCCESS", outputs=[{"response": {"status_code": 200, "body": {}}},
                                       _record("r1", '{"label": "ok"}')])

        results, _ = self._results(provider, config, job)

        assert [result.custom_id for result in results] == ["r1"]

    def test_the_output_and_error_files_are_read(self, provider, config):
        job = _job("TIMEOUT_EXCEEDED", output_file="file-out", error_file="file-err")
        output = json.dumps(_record("r0", '{"label": "ok"}')) + "\n"
        errors = json.dumps(_record("r1", "", status_code=500)) + "\n\n"

        results, client = self._results(provider, config, job, output, errors)

        assert [call.args[0] for call in client.get.call_args_list[1:]] == [
            "https://api.mistral.ai/v1/files/file-out/content", "https://api.mistral.ai/v1/files/file-err/content",
        ]
        assert results[0].data == Answer(label="ok") and isinstance(results[1].error, AIProviderError)

    def test_the_files_win_over_inline_results(self, provider, config):
        # The files hold every result whatever the job's size; an inline list may not.
        job = _job("SUCCESS", outputs=[_record("r9", '{"label": "inline"}')], output_file="file-out")
        output = json.dumps(_record("r0", '{"label": "ok"}'))

        results, _ = self._results(provider, config, job, output)

        assert [result.custom_id for result in results] == ["r0"]

    def test_a_job_answer_without_an_id_is_a_provider_error(self, provider, config):
        patcher, _ = _sync_client(_response(payload={"status": "QUEUED"}))
        try:
            with pytest.raises(AIProviderError):
                provider.get_batch_sync("job-1", config)
        finally:
            patcher.stop()

    def test_a_result_file_that_is_not_json_lines_is_an_error(self, provider, config):
        job = _job("SUCCESS", output_file="file-out")

        with pytest.raises(AIProviderError):
            self._results(provider, config, job, "not json\n")

    @pytest.mark.parametrize("status", ["QUEUED", "RUNNING", "CANCELLATION_REQUESTED"])
    def test_results_of_a_job_still_running_are_refused_before_any_file_is_read(self, provider, config, status):
        patcher, client = _sync_client(_response(payload=_job(status, output_file="file-out")))
        try:
            with pytest.raises(ValueError):
                provider.get_json_batch_results_sync("job-1", config, Answer)
        finally:
            patcher.stop()

        assert client.get.call_count == 1

    def test_a_count_that_is_not_a_number_is_a_provider_error(self, provider, config):
        patcher, _ = _sync_client(_response(payload=_job("QUEUED", total_requests="many")))
        try:
            with pytest.raises(AIProviderError):
                provider.get_batch_sync("job-1", config)
        finally:
            patcher.stop()


class TestMistralBatchAsync:

    @pytest.mark.asyncio
    async def test_a_job_is_read_on_its_url(self, provider, config):
        patcher, client = _async_client(_response(payload=_job("SUCCESS")))
        try:
            job = await provider.get_batch("job-1", config)
        finally:
            patcher.stop()

        assert client.get.call_args.args[0] == "https://api.mistral.ai/v1/batch/jobs/job-1"
        assert job.state is AIBatchState.COMPLETED

    @pytest.mark.asyncio
    async def test_a_job_is_cancelled_on_its_own_url(self, provider, config):
        patcher, client = _async_client(_response(payload=_job("CANCELLATION_REQUESTED")), method="post")
        try:
            job = await provider.cancel_batch("job-1", config)
        finally:
            patcher.stop()

        assert client.post.call_args.args[0] == "https://api.mistral.ai/v1/batch/jobs/job-1/cancel"
        assert job.state is AIBatchState.PENDING

    @pytest.mark.asyncio
    async def test_results_are_read_from_the_files(self, provider, config):
        job = _job("CANCELLED", output_file="file-out", error_file="file-err")
        output = json.dumps(_record("r0", '{"label": "ok"}'))
        errors = json.dumps(_record("r1", "", status_code=429))
        patcher, client = _async_client(_response(payload=job), _response(text=output), _response(text=errors))
        try:
            results = await provider.get_json_batch_results("job-1", config, Answer)
        finally:
            patcher.stop()

        assert "params" not in client.get.call_args_list[0].kwargs
        assert results[0].data == Answer(label="ok") and isinstance(results[1].error, AIRateLimitError)

    @pytest.mark.asyncio
    async def test_results_of_a_job_still_running_are_refused(self, provider, config):
        patcher, client = _async_client(_response(payload=_job("RUNNING", output_file="file-out")))
        try:
            with pytest.raises(ValueError):
                await provider.get_json_batch_results("job-1", config, Answer)
        finally:
            patcher.stop()

        assert client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_without_result_files_the_job_is_read_again_inline(self, provider, config):
        job = _job("SUCCESS", outputs=[_record("r0", '{"label": "ok"}')])
        patcher, client = _async_client(_response(payload=job), _response(payload=job))
        try:
            [result] = await provider.get_json_batch_results("job-1", config, Answer)
        finally:
            patcher.stop()

        assert "params" not in client.get.call_args_list[0].kwargs
        assert client.get.call_args_list[1].kwargs["params"] == {"inline": "true"}
        assert result.data == Answer(label="ok")

    @pytest.mark.asyncio
    async def test_a_timeout_is_an_ai_timeout(self, provider, config):
        patcher, _ = _async_client(httpx.TimeoutException("slow"))
        try:
            with pytest.raises(AITimeoutError):
                await provider.get_batch("job-1", config)
        finally:
            patcher.stop()


class TestMistralBatchFiles:

    def test_a_finished_job_s_input_output_and_error_files_are_deleted(self, provider, config):
        job = _job("SUCCESS", input_files=["file-in"], output_file="file-out", error_file="file-err")
        deleted = _response(payload={"deleted": True})
        patcher, client = _sync_client(_response(payload=job))
        client.delete.side_effect = [deleted, deleted, deleted]
        try:
            count = provider.delete_batch_files_sync("job-1", config)
        finally:
            patcher.stop()

        assert client.get.call_args.args[0] == "https://api.mistral.ai/v1/batch/jobs/job-1"
        assert [call.args[0] for call in client.delete.call_args_list] == [
            "https://api.mistral.ai/v1/files/file-in", "https://api.mistral.ai/v1/files/file-out",
            "https://api.mistral.ai/v1/files/file-err"]
        assert count == 3

    @pytest.mark.parametrize("status", ["QUEUED", "RUNNING"])
    def test_the_files_of_a_job_still_running_are_kept(self, provider, config, status):
        patcher, client = _sync_client(_response(payload=_job(status, input_files=["file-in"])))
        try:
            with pytest.raises(ValueError):
                provider.delete_batch_files_sync("job-1", config)
        finally:
            patcher.stop()

        client.delete.assert_not_called()

    def test_a_file_not_deleted_is_logged_and_not_counted(self, provider, config, caplog):
        job = _job("SUCCESS", input_files=["file-in"], output_file="file-out")
        patcher, client = _sync_client(_response(payload=job))
        client.delete.side_effect = [_response(status_code=500), _response(payload={"deleted": True})]
        try:
            count = provider.delete_batch_files_sync("job-1", config)
        finally:
            patcher.stop()

        assert count == 1
        assert "file-in not deleted: HTTP 500" in caplog.text

    def test_a_file_already_deleted_counts_as_gone_without_warning(self, provider, config, caplog):
        job = _job("SUCCESS", input_files=["file-in"], output_file="file-out")
        patcher, client = _sync_client(_response(payload=job))
        client.delete.side_effect = [_response(status_code=404), _response(payload={"deleted": True})]
        try:
            count = provider.delete_batch_files_sync("job-1", config)
        finally:
            patcher.stop()

        assert count == 2
        assert "not deleted" not in caplog.text

    def test_a_provider_without_batch_jobs_says_so(self, config):
        with pytest.raises(NotImplementedError):
            AnthropicProvider().delete_batch_files_sync("job", config)

    @pytest.mark.asyncio
    async def test_the_async_twin_deletes_the_same_files(self, provider, config):
        job = _job("CANCELLED", input_files=["file-in"], error_file="file-err")
        patcher, client = _async_client(_response(payload=job))
        client.delete.side_effect = [_response(payload={"deleted": True}), httpx.ConnectError("down")]
        try:
            count = await provider.delete_batch_files("job-1", config)
        finally:
            patcher.stop()

        assert [call.args[0] for call in client.delete.call_args_list] == [
            "https://api.mistral.ai/v1/files/file-in", "https://api.mistral.ai/v1/files/file-err"]
        assert count == 1


class TestAIServiceBatch:

    @pytest.fixture(autouse=True)
    def _mistral(self, provider):
        with patch.object(AIService, "get_provider", return_value=provider):
            yield

    def test_each_request_gets_the_endpoint_s_system_prompt(self, provider, config):
        with patch.object(provider, "submit_json_batch_sync", return_value="job") as submit:
            AIService.submit_json_batch_sync(_requests(1), config, Answer, {"origin": "test"})

        sent, endpoint, schema, metadata, timeout_hours = submit.call_args.args
        assert sent[0].custom_id == "r0" and sent[0].messages[0] == {"role": "system", "content": "Classify."}
        assert (endpoint, schema, metadata, timeout_hours) == (config, Answer, {"origin": "test"}, None)

    def test_the_files_are_deleted_by_the_provider(self, provider, config):
        with patch.object(provider, "delete_batch_files_sync", return_value=3) as delete:
            assert AIService.delete_batch_files_sync("job-1", config) == 3

        delete.assert_called_once_with("job-1", config)

    def test_a_text_field_cut_at_its_max_length_is_an_error_not_an_answer(self, provider, config):
        results = [AIBatchResult(custom_id="r0", data=ShortAnswer(label="abcde")),
                   AIBatchResult(custom_id="r1", data=ShortAnswer(label="ab"))]
        with patch.object(provider, "get_json_batch_results_sync", return_value=results):
            checked = AIService.get_json_batch_results_sync("job-1", config, ShortAnswer)

        assert checked[0].data is None and isinstance(checked[0].error, AIResponseTruncatedError)
        assert checked[1] == results[1]

    @pytest.mark.asyncio
    async def test_the_async_submit_gets_the_endpoint_s_system_prompt(self, provider, config):
        with patch.object(provider, "submit_json_batch", AsyncMock(return_value="job")) as submit:
            assert await AIService.submit_json_batch(_requests(1), config, Answer, timeout_hours=6) == "job"

        sent, endpoint, schema, metadata, timeout_hours = submit.call_args.args
        assert sent[0].messages[0] == {"role": "system", "content": "Classify."}
        assert (endpoint, schema, metadata, timeout_hours) == (config, Answer, None, 6)

    @pytest.mark.asyncio
    async def test_the_async_results_are_checked_for_max_length(self, provider, config):
        results = [AIBatchResult(custom_id="r0", data=ShortAnswer(label="abcde"))]
        with patch.object(provider, "get_json_batch_results", AsyncMock(return_value=results)):
            [checked] = await AIService.get_json_batch_results("job-1", config, ShortAnswer)

        assert checked.data is None and isinstance(checked.error, AIResponseTruncatedError)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method", ["get_batch", "cancel_batch", "delete_batch_files"])
    async def test_the_async_job_calls_reach_the_provider(self, provider, config, method):
        with patch.object(provider, method, AsyncMock(return_value="job")) as call:
            assert await getattr(AIService, method)("job-1", config) == "job"

        call.assert_awaited_once_with("job-1", config)

    @pytest.mark.parametrize("method", ["get_batch_sync", "cancel_batch_sync"])
    def test_the_sync_job_calls_reach_the_provider(self, provider, config, method):
        with patch.object(provider, method, return_value="job") as call:
            assert getattr(AIService, method)("job-1", config) == "job"

        call.assert_called_once_with("job-1", config)
