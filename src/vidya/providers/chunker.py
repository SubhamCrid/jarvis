"""
SentenceChunker for translating token streams into natural speech sentences for streaming TTS.
"""

import re
import logging
from typing import List, Optional

logger = logging.getLogger("vidya.providers.chunker")


class SentenceChunker:
    """
    Accumulates streaming LLM tokens and yields complete sentences when delimiters
    ('.', '?', '!', '\n') are encountered.
    """

    # Sentence boundary regex
    SENTENCE_END_REGEX = re.compile(r"([^.!?\n]+[.!?\n]+)")

    def __init__(self, min_sentence_len: int = 15) -> None:
        self.min_sentence_len = min_sentence_len
        self._buffer: str = ""

    def add_token(self, token: str) -> List[str]:
        """
        Add LLM token and return any completed sentence chunks.
        """
        self._buffer += token
        chunks = []

        while True:
            match = self.SENTENCE_END_REGEX.search(self._buffer)
            if not match:
                break
            
            end_pos = match.end()
            sentence = self._buffer[:end_pos].strip()
            self._buffer = self._buffer[end_pos:]

            if sentence:
                chunks.append(sentence)

        return chunks

    def flush(self) -> Optional[str]:
        """Flush remaining buffer at the end of LLM generation stream."""
        remaining = self._buffer.strip()
        self._buffer = ""
        return remaining if remaining else None

    def reset(self) -> None:
        self._buffer = ""
