# --- BEGIN GENERATED CODE ---
import collections.abc
import re
from typing import Any, Dict, List, Set, Tuple, Iterable

_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def _split_words_lower(text: str) -> List[str]:
    # Extract alphanumeric “words” case-insensitively.
    return _WORD_RE.findall(text.lower())


def _is_word_token(tok: str) -> bool:
    # Treat tokens consisting solely of alphanumeric chars as word tokens.
    # This aligns with tests (letters/digits == words; spaces/punct/markdown == separators).
    return tok.isalnum()


class _TrieNode:
    __slots__ = ("children", "values", "max_child_word_len")

    def __init__(self) -> None:
        self.children: Dict[str, _TrieNode] = {}
        self.values: Set[Any] = set()
        self.max_child_word_len: int = 0

    def child_for(self, word: str) -> "._TrieNode | None":
        return self.children.get(word)


def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index (trie) from a dictionary for fast lookup of words and
    compound phrases. Dictionary lookup is case-insensitive and ignores non-word
    separators inside dictionary keys.
    """
    root = _TrieNode()
    for key, meaning in dictionary.items():
        words = _split_words_lower(str(key))
        if not words:
            continue  # skip entries with no alphanumeric words
        node = root
        for w in words:
            child = node.children.get(w)
            if child is None:
                child = _TrieNode()
                node.children[w] = child
                # Track the maximum length of child words for bounded lookahead
                if len(w) > node.max_child_word_len:
                    node.max_child_word_len = len(w)
            else:
                if len(w) > node.max_child_word_len:
                    node.max_child_word_len = len(w)
            node = child
        node.values.add(meaning)
    return root


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary index. Matches are:
      - Case-insensitive.
      - Aligned to token boundaries (no mid-token matches).
      - Multi-word phrases require at least one separator token between words;
        inner separators are included (annotated) while leading/trailing separators
        outside the phrase are not.
      - Single dictionary words may span multiple adjacent word tokens (concatenation).
    """
    root = dictionary_index  # type: ignore[assignment]
    if not isinstance(root, _TrieNode):
        raise TypeError("dictionary_index must be built by build_dictionary_index()")

    toks: List[str] = list(tokens)
    n = len(toks)
    if n == 0:
        return []

    is_word = [_is_word_token(t) for t in toks]
    low = [t.lower() for t in toks]
    ann: List[Set[Any]] = [set() for _ in range(n)]

    # Helper: from node and token position pos (must be a word token),
    # find all child words that match by concatenating whole adjacent word tokens.
    def match_child_words(node: _TrieNode, pos: int) -> List[Tuple[_TrieNode, int]]:
        if pos >= n or not is_word[pos]:
            return []
        res: List[Tuple[_TrieNode, int]] = []
        concat = ""
        i = pos
        max_len = node.max_child_word_len
        # To prune quickly when no child starts with current concat
        child_keys = node.children.keys()
        while i < n and is_word[i] and len(concat) < max_len:
            concat += low[i]
            child = node.children.get(concat)
            if child is not None:
                res.append((child, i))
            # Check if any child key starts with current concat; if not, break early
            has_prefix = False
            # Small optimization: if an exact child matched and its length equals max_len,
            # we still allow longer matches; otherwise scan prefixes.
            for k in child_keys:
                if k.startswith(concat):
                    has_prefix = True
                    break
            if not has_prefix:
                break
            i += 1
        return res

    # Add all meanings in values to tokens in span [s, e] inclusive.
    def annotate_span(s: int, e: int, values: Set[Any]) -> None:
        if not values:
            return
        for i in range(s, e + 1):
            ann[i].update(values)

    # DFS from a starting word token s through the trie.
    def traverse_from(s: int) -> None:
        # First word must start exactly at s.
        first_matches = match_child_words(root, s)
        if not first_matches:
            return

        # Stack entries: (node, span_start, last_word_end_index)
        stack: List[Tuple[_TrieNode, int, int]] = []
        for node, end_idx in first_matches:
            # Annotate any terminal match at this node (single-word or first part of a phrase)
            if node.values:
                annotate_span(s, end_idx, node.values)
            stack.append((node, s, end_idx))

        while stack:
            node, span_start, last_end = stack.pop()
            # To proceed to next dictionary word, we require >=1 separator token
            sep_start = last_end + 1
            if sep_start >= n or is_word[sep_start]:
                continue  # no separator, cannot extend a multi-word phrase
            # Skip one or more separators (these will be included in span once extended)
            next_word_pos = sep_start
            while next_word_pos < n and not is_word[next_word_pos]:
                next_word_pos += 1
            if next_word_pos >= n or not is_word[next_word_pos]:
                continue  # no next word to extend to

            # Try to match the next word from the trie at this node
            next_matches = match_child_words(node, next_word_pos)
            for child, end_idx in next_matches:
                # Annotate terminal phrase up to this end (includes inner separators)
                if child.values:
                    annotate_span(span_start, end_idx, child.values)
                # Continue extending further
                stack.append((child, span_start, end_idx))

    for s in range(n):
        if is_word[s]:
            traverse_from(s)

    return [(toks[i], ann[i]) for i in range(n)]
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


