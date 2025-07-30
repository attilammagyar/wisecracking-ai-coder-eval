# --- BEGIN GENERATED CODE ---
import collections.abc
from typing import Any, Dict, List, Optional, Set, Tuple

# Helper: Is this token a "word" token?
def is_word_token(token: str) -> bool:
    # We'll treat any token with at least one alphanumeric character as a word
    return any(c.isalnum() for c in token)

def normalize_token(token: str) -> str:
    return token.lower()

class TrieNode:
    __slots__ = ('children', 'entries')
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.entries: Set[Any] = set()  # Set of dictionary entry ids

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Builds a case-insensitive trie for multi-word phrases, and a single-token lookup.
    Phrases are tokenized simply by splitting on whitespace and common punct, case ignored.
    """
    # Single words: {norm_word: {entry_id, ...}}
    single_word: Dict[str, Set[Any]] = collections.defaultdict(set)

    # Trie root for multi-word (and single-word, for consistency)
    trie_root = TrieNode()

    for phrase, entry_id in dictionary.items():
        # Tokenize phrase: treat any sequence of alnum chars as word tokens,
        # and anything else as separator (collapse multiple separators)
        normalized = []
        buf = ''
        for ch in phrase:
            if ch.isalnum():
                buf += ch
            else:
                if buf:
                    normalized.append(buf.lower())
                    buf = ''
                if not ch.isspace():
                    normalized.append(ch)
                else:
                    normalized.append(' ')
        if buf:
            normalized.append(buf.lower())
        # Remove consecutive separators and strip leading/trailing separators.
        phrase_tokens = []
        last_is_word = None
        for tok in normalized:
            is_word = any(c.isalnum() for c in tok)
            if last_is_word is None or is_word != last_is_word or is_word:
                phrase_tokens.append(tok)
            last_is_word = is_word
        # Remove leading/trailing non-words for phrase matching
        while phrase_tokens and not any(c.isalnum() for c in phrase_tokens[0]):
            phrase_tokens.pop(0)
        while phrase_tokens and not any(c.isalnum() for c in phrase_tokens[-1]):
            phrase_tokens.pop()
        if not phrase_tokens:
            continue
        if len([t for t in phrase_tokens if any(c.isalnum() for c in t)]) == 1:
            # Single-word entry
            word = next(t for t in phrase_tokens if any(c.isalnum() for c in t))
            single_word[word.lower()].add(entry_id)
        # Insert into trie
        node = trie_root
        for tok in phrase_tokens:
            norm = tok.lower()
            if norm not in node.children:
                node.children[norm] = TrieNode()
            node = node.children[norm]
        node.entries.add(entry_id)
    # Dump dictionary index
    return {
        "single_word": single_word,
        "trie_root": trie_root,
    }

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[Tuple[str, Set]]:
    tokens = list(tokens)
    n = len(tokens)
    single_word: Dict[str, Set[Any]] = dictionary_index['single_word']
    trie_root: TrieNode = dictionary_index['trie_root']
    # Token type classification, for reuse:
    is_word = [is_word_token(tok) for tok in tokens]
    norm_token = [normalize_token(tok) for tok in tokens]

    # For each token, collect all dictionary entries it participates in
    annotations: List[Set[Any]] = [set() for _ in range(n)]

    # Single word entries (per token)
    for i, (tok, wordy) in enumerate(zip(tokens, is_word)):
        if wordy:
            for entry in single_word.get(norm_token[i], ()):
                annotations[i].add(entry)

    # Compound phrase search
    # Start a matching window at each position in tokens
    for start in range(n):
        i = start
        positions: List[int] = []
        node = trie_root
        word_count = 0
        # Only start matching on a word token (phrases don't start with separators)
        if not is_word[i]:
            continue
        j = i
        while j < n:
            tok = norm_token[j]
            # Only step in trie on word tokens (phrase trie only includes word tokens and separators as nodes)
            key = tok if is_word[j] else tok  # uses separator tokens as nodes too
            # Match step: only allow separators if not over the edge (avoid leading/trailing separators)
            if key in node.children:
                node = node.children[key]
                positions.append(j)
                if is_word[j]:
                    word_count += 1
                    last_word = j  # For later use
                # If phrase ends with a separator, that's ok, but only annotate inner separators later
                if node.entries and word_count >= 1:
                    # Determine which tokens to annotate: start must be word, end must be word,
                    # annotate all interior (including separators inside the matched region)
                    first_idx = positions[0]
                    last_idx = positions[-1]
                    # Ensure first and last are word tokens
                    if is_word[first_idx] and is_word[last_idx]:
                        # Annotate all positions in [first_idx, last_idx]
                        for k in range(first_idx, last_idx + 1):
                            # Only annotate separators if not first or last position
                            if is_word[k] or (first_idx < k < last_idx):
                                annotations[k].update(node.entries)
                j += 1
            else:
                # For non-word token: skip, if in between words; for word-token: unmatched, break
                if not is_word[j]:
                    positions.append(j)
                    j += 1
                    continue
                else:
                    break

    for i in range(n):
        yield (tokens[i], annotations[i])

# Hasta la vista, baby! Time to send that fiver to my non-existent bank account.
# --- END GENERATED CODE ---

def test_empty_sentence():
    dictionary = {}
    tokens = []

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = []
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_token_not_in_dictionary():
    """
    When a token is not found in the dictionary
    then it should not be annotated with anything.
    """
    dictionary = {}
    tokens = ["AAA"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_token_found_in_dictionary():
    """
    When a token is found in the dictionary
    then the token should be annotated with its dictionary entry.
    """
    dictionary = {"AAA": 1}
    tokens = ["AAA"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_case_insensitive_dictionary_lookup():
    """
    Dictionary lookup should be case-insensitive.
    """
    dictionary = {"AAA": 1, "BBB": 2}
    tokens = ["Aaa", "bbb"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("Aaa", {1}), ("bbb", {2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase():
    """
    All tokens in a compound phrase which is found in the dictionary
    should be annotated with the dictionary entry of the phrase.
    """
    dictionary = {"AAA BBB": 1}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), (" ", {1}), ("BBB", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase_and_individual_word():
    """
    When a token is found in the dictionary both as an individual word and as part of a compound phrase
    then its annotations should include the dictionary entries of both the phrase and the individual word as well.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA BBB": 3}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {3, 1}), (" ", {3}), ("BBB", {3, 2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrases_word_separation():
    """
    Compound phrase dictionary lookup should be insensitive to word separators.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA, BBB": 3}
    tokens = ["AAA", " ", "*", "BBB", "*"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {3, 1}), (" ", {3}), ("*", {3}),("BBB", {3, 2}), ("*", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_leading_and_trailing_separators_around_compound_phrase():
    """
    The leading and trailing word separators should not be considered
    parts of a compound phrase.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAA BBB": 3}
    tokens = [" ", "AAA", " ", "BBB", " "]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [(" ", set()), ("AAA", {3, 1}), (" ", {3}), ("BBB", {3, 2}), (" ", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_separated_tokens_do_not_make_a_compound_word():
    """
    When tokens are separated by non-word characters
    then they should not be considered a compound word.
    """
    dictionary = {"AAA": 1, "BBB": 2, "AAABBB": 3}
    tokens = ["AAA", " ", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), (" ", set()), ("BBB", {2})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_word_tokens_missing_from_dictionary():
    """
    Compound words may contain tokens which are not listed in the dictionary
    as individual words.
    """
    dictionary = {"AAABBB": 1}
    tokens = ["AAA", "BBB"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", {1}), ("BBB", {1})]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_compound_phrase_overlap():
    """
    Tokens in overlapping compound phrases should be annotated with the
    dictionary entries for all compound phrases in which they participate.
    """
    dictionary = {
        "AAA": 1,
        "BBB": 2,
        "CCC": 3,
        "AAA BBB": 4,
        "BBB CCC": 5,
        "CCC CCC": 6,
    }
    tokens = ["AAA", " ", "BBB", " ", "CCC", " ", "CCC", " ", "CCC"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("AAA", {4, 1}),
        (" ", {4}),
        ("BBB", {5, 4, 2}),
        (" ", {5}),
        ("CCC", {6, 5, 3}),
        (" ", {6}),
        ("CCC", {6, 3}),
        (" ", {6}),
        ("CCC", {6, 3}),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_nested_compound_phrases():
    """
    When a compound phrase itself is a part of a larger compound phrase
    then its tokens should be annotated with the dictionary entries for all the nested compound phrases.
    """
    dictionary = {
        "AAA": 1,
        "BBB": 2,
        "CCC": 3,
        "DDD": 4,
        "EEE": 5,
        "AAA BBB CCC DDD EEE": 6,
        "BBB CCC DDD": 7,
        "BBB CCC": 8,
    }
    tokens = ["AAA", " ", "BBB", " ", "CCC", " ", "DDD", " ", "EEE"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("AAA", {6, 1}),
        (" ", {6}),
        ("BBB", {6, 7, 8, 2}),
        (" ", {6, 7, 8}),
        ("CCC", {6, 7, 8, 3}),
        (" ", {6, 7}),
        ("DDD", {6, 7, 4}),
        (" ", {6}),
        ("EEE", {6, 5}),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_no_midtoken_match():
    """
    Dictionary entry match must occur at token end.
    """
    dictionary = {"AA": 1, "AAA BBB": 2, "CC": 3, "CCCDDD": 4}
    tokens = ["AAA", " ", "BBBCCC", "CCC", "DDDEEE"]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [("AAA", set()), (" ", set()), ("BBBCCC", set()), ("CCC", set()), ("DDDEEE", set())]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def test_real_life_example():
    dictionary = {
        "a": 1,
        "black": 2,
        "swan": 3,
        "black swan": 4,
        "event": 5,
        "black swan event": 6,
        "would": 7,
        "occur": 8,
        "less": 9,
        "than": 10,
        "once": 11,
        "in": 12,
        "blue": 13,
        "moon": 14,
        "blue moon": 15,
        "once in a blue moon": 16,
    }
    tokens = [
        "A", " ", "black", " ", "swan", " ", "event", " ", "would", " ",
        "occur", " ", "less", " ", "than", " ", "once", " ", "in", " ", "a",
        " ", "blue", " ", "moon", ".",
    ]

    dictionary_index = build_dictionary_index(dictionary)
    annotated_tokens = list(annotate(tokens, dictionary_index))

    expected = [
        ("A", {1}),
        (" ", set()),
        ("black", {2, 4, 6}),
        (" ", {4, 6}),
        ("swan", {3, 4, 6}),
        (" ", {6}),
        ("event", {5, 6}),
        (" ", set()),
        ("would", {7}),
        (" ", set()),
        ("occur", {8}),
        (" ", set()),
        ("less", {9}),
        (" ", set()),
        ("than", {10}),
        (" ", set()),
        ("once", {11, 16}),
        (" ", {16}),
        ("in", {12, 16}),
        (" ", {16}),
        ("a", {1, 16}),
        (" ", {16}),
        ("blue", {13, 15, 16}),
        (" ", {15, 16}),
        ("moon", {14, 15, 16}),
        (".", set()),
    ]
    assert annotated_tokens == expected, f"{expected=}, {annotated_tokens=}"

def perf_test():
    import random
    import time

    dictionary = {
        "a": 1,
        "black": 2,
        "swan": 3,
        "black swan": 4,
        "event": 5,
        "black swan event": 6,
        "would": 7,
        "occur": 8,
        "less": 9,
        "than": 10,
        "once": 11,
        "in": 12,
        "blue": 13,
        "moon": 14,
        "blue moon": 15,
        "once in a blue moon": 16,
    }
    tokens = [
        "A", " ", "black", " ", "swan", " ", "event", " ", "would", " ",
        "occur", " ", "less", " ", "than", " ", "once", " ", "in", " ", "a",
        " ", "blue", " ", "moon", ".",
    ]
    letters = "abcdefghijklmnopqrstuvwxyz"

    while len(dictionary) < 1000:
        random_word = "".join([random.choice(letters) for i in range(15)])
        random_expr = (
            "".join([random.choice(letters) for i in range(7)])
            + " "
            + "".join([random.choice(letters) for i in range(7)])
        )
        dictionary[random_word] = len(dictionary)
        dictionary[random_expr] = len(dictionary)

    for i in range(6):
        tokens = tokens + tokens

    begin = time.time()

    for i in range(100):
        tokens_copy = list(tokens)
        dictionary_copy = dict(dictionary)
        dictionary_index = build_dictionary_index(dictionary_copy)
        annotated_tokens = list(annotate(tokens_copy, dictionary_index))

    end = time.time()

    return end - begin


def run_tests():
    import json
    import sys

    module = sys.modules[__name__]

    tests = []

    for name, value in globals().items():
        if name.startswith("test_") and callable(value) and value.__code__.co_argcount == 0:
            tests.append(value)

    passed = 0
    failed = 0
    failures = []

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as exc:
            failed += 1
            failures.append(f"{type(exc)} {exc}")

    perf = perf_test()

    results = {
        "passed": passed,
        "failed": failed,
        "perf": perf,
        "failures": failures,
    }

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    run_tests()


