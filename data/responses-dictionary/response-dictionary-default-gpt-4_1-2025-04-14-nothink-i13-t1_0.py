# --- BEGIN GENERATED CODE ---
import collections.abc
from typing import Dict, Set, List, Tuple, Any

# Helper: Checks if a token is a word token or a separator.
def is_word_token(token: str) -> bool:
    # For our purpose, treat alphanumeric as word, the rest as separators.
    # This means that "AAA", "BBB", "a", "black", "swan", "event", etc. are word tokens.
    # Everything else (space, comma, asterisk, punctuation, markdown, etc.) is not.
    # A word token has at least 1 alphanumeric char; adjust logic if needed.
    return any(c.isalnum() for c in token)

def normalize_token(token: str) -> str:
    # For matching, lower-case everything.
    return token.lower()

def tokenize_dict_phrase(phrase: str) -> List[str]:
    """
    Tokenize a dictionary phrase into normalized tokens: alternate word/separator.
    For this problem, we can use whitespace as a separator in phrases,
    and keep them as explicit " " tokens for separators.
    Note: Dictionary entries may use spaces or other separators, but for matching,
    we normalize all separators to a single separator (e.g., " ").

    Returns a list of tokens: word tokens and separator tokens alternate.
    E.g., 'AAA, BBB' --> ['aaa', ' ', 'bbb']
    """
    import re
    tokens = []
    # Split on groups of non-word characters, keeping those as separator tokens
    # Use capturing group to keep delimiters
    parts = re.split(r'(\W+)', phrase)
    for part in parts:
        if not part:
            continue
        if any(c.isalnum() for c in part):
            tokens.append(normalize_token(part))
        else:
            # Normalize any sequence of separator chars to a single " " (space)
            tokens.append(" ")
    # Remove leading/trailing separators, collapse multiple separators to one
    # We'll also ensure alternation: word/separator/word...
    result = []
    last_was_sep = None
    for t in tokens:
        is_sep = t == " "
        if is_sep:
            if last_was_sep:
                continue  # skip duplicate separator
        result.append(t)
        last_was_sep = is_sep
    # Remove leading/trailing separators for matching
    while result and result[0] == " ":
        result.pop(0)
    while result and result[-1] == " ":
        result.pop()
    return result

class TrieNode:
    __slots__ = ('children', 'entries')
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.entries: Set[Any] = set()  # set of dictionary entry IDs at this node

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a trie of normalized dictionary entries for phrase matching.
    """
    root = TrieNode()
    # Store all maximal phrase lengths for later optimization
    max_phrase_len = 0
    for key, value in dictionary.items():
        tokens = tokenize_dict_phrase(key)
        max_phrase_len = max(max_phrase_len, len(tokens))
        node = root
        for t in tokens:
            if t not in node.children:
                node.children[t] = TrieNode()
            node = node.children[t]
        node.entries.add(value)
    # Trie structure and info to facilitate scanning
    return (root, max_phrase_len)

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    # Prepare
    tokens = list(tokens)
    n = len(tokens)
    root, max_phrase_len = dictionary_index
    # Precompute for each token: type (word/separator) and normalized form
    token_tuples = []  # (is_word, normalized_token)
    for tok in tokens:
        is_word = is_word_token(tok)
        n_tok = normalize_token(tok)
        token_tuples.append((is_word, n_tok))
    # Prepare annotation sets for every token
    annotations = [set() for _ in range(n)]

    # For each position, try matching dictionary trie from that point onward
    pos = 0
    while pos < n:
        # Maximal span we might need to check
        cur_node = root
        match_positions = []  # list of matched positions in tokens for phrase
        # For alternation, we must mimic the dict phrase tokenization:
        # skip leading separators when starting a phrase match,
        # and always alternate word, sep, word, sep... (if exists)
        j = pos
        # Skip leading separators for phrase matching
        while j < n and not token_tuples[j][0]:
            j += 1
        i = j
        tokens_used_in_match = []  # indices into tokens
        trie_nodes_traversed = []
        expected_kind = True  # start at word
        while i < n:
            is_word, n_tok = token_tuples[i]
            if is_word != expected_kind:
                # Not matching the expected alternation for this match
                break
            # Try moving in the trie
            if n_tok in cur_node.children:
                cur_node = cur_node.children[n_tok]
                tokens_used_in_match.append(i)
                trie_nodes_traversed.append(cur_node)
                if cur_node.entries:
                    # We found a phrase ending at i (covers tokens_used_in_match).
                    # We must annotate all tokens covered, except for leading/trailing
                    # separators: for phrase spans >=2, only "inner" separators
                    # get annotation (if at all). For 1-token (single word) matches,
                    # only that token is annotated
                    # Find inner separators
                    for idx, t_idx in enumerate(tokens_used_in_match):
                        # For multi-token match:
                        # If this token is a separator:
                        # - If it is first or last in the match: skip
                        # - Else, annotate with this phrase id.
                        # Words: always annotate
                        if len(tokens_used_in_match) == 1:
                            # Only item - always annotate
                            annotations[t_idx].update(cur_node.entries)
                        else:
                            is_sep = not token_tuples[t_idx][0]
                            if is_sep:
                                if idx == 0 or idx == len(tokens_used_in_match) - 1:
                                    continue  # skip leading/trailing separators
                                annotations[t_idx].update(cur_node.entries)
                            else:
                                # word tokens: always annotate
                                annotations[t_idx].update(cur_node.entries)
            else:
                # No further match
                break
            # Alternate expectation: word, sep, word, sep, ...
            expected_kind = not expected_kind
            i += 1
        # END of scan forward from pos; Now handle the single-word/phrase matches that start exactly at pos
        # If the current token is a word (not starting from a separator), and if the trie has an immediate child matching this token
        if token_tuples[pos][0]:  # word
            node1 = root.children.get(token_tuples[pos][1])
            if node1 is not None and node1.entries:
                # Single-word dictionary match
                annotations[pos].update(node1.entries)
        # Next starting position
        pos += 1

    # Compose output
    return [(tokens[i], annotations[i]) for i in range(n)]
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


