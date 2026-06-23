from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.file_processor import compile_reference_text, extract_relevant


def _make_llm_mock(response: str) -> MagicMock:
    msg = MagicMock()
    msg.content = response
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client


def test_compile_reference_text_concatenates_files():
    mock_client = _make_llm_mock("Relevant: Software Engineer at Acme 2021-2024")
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = compile_reference_text([("cv.txt", b"Full resume text here")])
    assert "=== cv.txt ===" in result
    assert "Relevant: Software Engineer" in result


def test_compile_reference_text_caps_at_60k():
    # Each file returns 4000-char extraction; 20 files = 80k total before cap
    long_text = "A" * 4000
    mock_client = _make_llm_mock(long_text)
    files = [(f"file{i}.txt", b"content") for i in range(20)]
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = compile_reference_text(files)
    assert len(result) <= 60_100  # 60k + small truncation note
    assert "[truncated" in result


def test_compile_reference_text_skips_failed_extraction():
    def side_effect(**kwargs):
        raise RuntimeError("LLM error")

    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = side_effect
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = compile_reference_text([("bad.pdf", b"content"), ("ok.txt", b"real text")])
    # Both files fail LLM extraction; result should be empty string (no error raised)
    assert result == ""


def test_extract_relevant_caps_at_4000_chars():
    long_extraction = "X" * 5000
    mock_client = _make_llm_mock(long_extraction)
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = extract_relevant("doc.txt", b"some content")
    assert len(result) <= 4000
