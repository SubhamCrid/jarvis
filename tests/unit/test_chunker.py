"""
Unit tests for SentenceChunker.
"""

from vidya.providers.chunker import SentenceChunker


def test_sentence_chunker_delimiter_split():
    chunker = SentenceChunker()
    
    c1 = chunker.add_token("Hello ")
    assert c1 == []
    
    c2 = chunker.add_token("there! How ")
    assert c2 == ["Hello there!"]
    
    c3 = chunker.add_token("are you doing?")
    assert c3 == ["How are you doing?"]

    flushed = chunker.flush()
    assert flushed is None


def test_sentence_chunker_flush_remaining():
    chunker = SentenceChunker()
    chunker.add_token("This is a statement without ending punctuation")
    
    flushed = chunker.flush()
    assert flushed == "This is a statement without ending punctuation"
