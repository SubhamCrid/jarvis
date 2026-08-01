"""
SentenceChunker for translating token streams into natural speech sentences for streaming TTS.
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger("jarvis.providers.chunker")


class SentenceChunker:
    """
    Accumulates streaming LLM tokens and yields complete sentences or low-latency clause
    chunks when delimiters ('.', '?', '!', '\n', ';', and ',' / ':' after minimum length)
    are encountered.
    """

    # Regex matching valid sentence and clause boundaries:
    # 1. Exclamation or question marks followed by optional punctuation and whitespace or end-of-string: [!?]+[^\w\s]*(?=\s+|$)
    # 2. Period NOT inside a filename/number, followed by optional punctuation and mandatory whitespace or EOS: \.(?<!\b[a-zA-Z0-9]\.[a-zA-Z0-9])[^\w\s]*(?=\s+|$)
    # 3. Semicolon or Newline characters: [;\n]+
    # 4. Clause punctuation (comma, colon) followed by whitespace: [,:]\s+
    SENTENCE_SPLIT_REGEX = re.compile(
        r"(.*?(?:[!?]+[^\w\s]*(?=\s+|$)|(?<!\b[a-zA-Z0-9]\.[a-zA-Z0-9])\.(?![a-zA-Z0-9_\-\.])[^\w\s]*(?=\s+)|[;\n]+|[,:]\s+))",
        re.DOTALL
    )

    def __init__(self, min_sentence_len: int = 8) -> None:
        self.min_sentence_len = min_sentence_len
        self._buffer: str = ""
        self._last_sentence: str = ""
        self._sentence_count: int = 0

    def add_token(self, token: str) -> List[str]:
        """
        Add LLM token and return any completed sentence or clause chunks.
        """
        self._buffer += token
        chunks = []

        while True:
            match = self.SENTENCE_SPLIT_REGEX.search(self._buffer)
            if not match:
                break
            
            end_pos = match.end()
            sentence = self._buffer[:end_pos].strip()
            matched_text = match.group(1).strip()

            # If chunk ends with clause punctuation (comma/colon) but length is shorter than min_sentence_len,
            # wait for more tokens unless it's a full sentence terminator ('.', '!', '?', '\n', ';').
            is_clause_split = matched_text.endswith((',', ':'))
            if is_clause_split and len(sentence) < self.min_sentence_len:
                break

            self._buffer = self._buffer[end_pos:]

            if sentence:
                # Anti-repetition guard: skip identical duplicate sentences
                if sentence.lower() == self._last_sentence.lower():
                    logger.warning(f"Duplicate consecutive sentence detected and suppressed: '{sentence}'")
                    continue
                self._last_sentence = sentence
                self._sentence_count += 1
                chunks.append(sentence)

        return chunks

    def flush(self) -> Optional[str]:
        """Flush remaining buffer at the end of LLM generation stream."""
        remaining = self._buffer.strip()
        self._buffer = ""
        if remaining and remaining.lower() != self._last_sentence.lower():
            self._last_sentence = remaining
            self._sentence_count += 1
            return remaining
        return None

    def reset(self) -> None:
        self._buffer = ""
        self._last_sentence = ""
        self._sentence_count = 0
