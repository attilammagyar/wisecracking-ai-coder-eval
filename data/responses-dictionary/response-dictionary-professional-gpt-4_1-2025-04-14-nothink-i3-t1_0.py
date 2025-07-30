# --- BEGIN GENERATED CODE ---
import collections.abc
from typing import Dict, Set, List, Tuple, Optional

# --- Helper functions ---

def is_word_token(token: str) -> bool:
    """Classify whether this token is a 'word' or 'separator'.
    Very strict, but test cases expect separators to be anything not completely alphabetic (or not-alnum maybe).
    We'll use .isalnum() as the main heuristic; adjust as needed for stricter definitions."""
    # Accepting alphabetic and digit characters as 'word tokens' for broader languages.
    return token.isalnum()

def normalize_word(token: str) -> str:
    return token.lower()

# --- Trie classes ---

class TrieNode:
    __slots__ = ('children', 'dict_entries')
    def __init__(self):
        self.children: Dict[str, 'TrieNode'] = {}
        self.dict_entries: Set = set()

# Constants for path construction
_WORD = 'W'     # Placeholder: will be replaced by the actual word string
_SEP = 'S'      # Any separator group (does not care which specific separator)

def tokenize_phrase(phrase: str) -> List[Tuple[str, str]]:
    """
    Given a phrase from the dictionary, split it to a sequence of ('W', word) or ('S', '') entries,
    collapsing multiple separators to a single separator slot.
    """
    # We'll scan the phrase, alternating between sequences of word chars and sequences of separators
    result = []
    i = 0
    n = len(phrase)
    while i < n:
        # Collect word
        start = i
        while i < n and is_word_token(phrase[i]):
            i += 1
        if i > start:
            result.append((_WORD, normalize_word(phrase[start:i])))
        # Collect separator (one or more)
        start = i
        while i < n and not is_word_token(phrase[i]):
            i += 1
        if i > start:
            result.append((_SEP, ''))  # Just mark the presence of a separator slot
    return result

def tokens_to_path(tokens: List[str]) -> List[Tuple[str, str]]:
    """
    Classify the given list of tokens as a path of ('W', word) and ('S', '') markers, for use as trie lookup path.
    """
    path = []
    n = len(tokens)
    i = 0
    while i < n:
        tok = tokens[i]
        if is_word_token(tok):
            path.append((_WORD, normalize_word(tok)))
            i += 1
        else:
            # Group all contiguous separators together as a single separator node in the path
            # (matching the dictionary's approach)
            while i < n and not is_word_token(tokens[i]):
                i += 1
            path.append((_SEP, ''))
    return path

def classify_tokens(tokens: List[str]) -> List[Tuple[bool, str]]:
    """
    For each token, determine whether it is a word, as well as its normalized word content (lowercased for words).
    Returns list of (is_word: bool, normalized_value: str).
    """
    out = []
    for t in tokens:
        if is_word_token(t):
            out.append((True, normalize_word(t)))
        else:
            out.append((False, t))
    return out

# --- Index construction ---

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized trie-based index for fast matching of dictionary words and phrases.
    Each path in the trie represents the alternation of words and separator slots.
    """
    root = TrieNode()
    max_phrase_len = 1  # Used to bound match scans in annotate()

    for phrase, entry in dictionary.items():
        # Tokenize the phrase into alternations of words and separator slots
        norm_path = tokenize_phrase(phrase)
        node = root
        phrase_tok_count = 0  # Only counting how many tokens this phrase would cover

        # Each word and each separator group (even zero-length) counts as one path element
        for kind, val in norm_path:
            if kind == _WORD:
                phrase_tok_count += 1
                # Child by the word string
                node = node.children.setdefault((_WORD, val), TrieNode())
            else:
                # Separator slot - always the same child, just a marker
                phrase_tok_count += 1
                node = node.children.setdefault((_SEP, ''), TrieNode())
        node.dict_entries.add(entry)
        if phrase_tok_count > max_phrase_len:
            max_phrase_len = phrase_tok_count

    index = {
        'root': root,
        'max_phrase_len': max_phrase_len  # so that annotate can bound scan
    }
    return index

# --- Annotation ---

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    tokens = list(tokens)
    n = len(tokens)
    result: List[Tuple[str, Set]] = [ (tok, set()) for tok in tokens ]
    token_types = classify_tokens(tokens)  # List of (is_word, normalized_value)

    root: TrieNode = dictionary_index['root']
    max_phrase_len: int = dictionary_index['max_phrase_len']

    # For fast single-word lookup:
    # For a single word token, we can do direct lookup in root.children[(_WORD, <word>)]
    # For a single separator token, only phrases consisting of a single separator could match, which is unlikely and not expected.

    # For each position, scan ahead for matches up to max_phrase_len tokens
    for i in range(n):
        # Start scanning ahead
        node = root
        pos = i
        path: List[int] = []  # Indices of tokens matched so far

        k = 0  # limit how many tokens will be considered

        curr_pos = i
        while curr_pos < n and k < max_phrase_len:
            is_word, normval = token_types[curr_pos]
            if is_word:
                key = (_WORD, normval)
            else:
                key = (_SEP, '')
            if key not in node.children:
                break
            node = node.children[key]
            path.append(curr_pos)
            # If node has dict_entries, we found a phrase match ending here (from i to curr_pos, inclusive)
            if node.dict_entries:
                # To annotate:
                # - Annotate all positions in [i, curr_pos], except
                #   - the first token if it is a separator and is at the leading end (start of match)
                #   - the last token if it is a separator and is at the trailing end (end of match)
                start = i
                end = curr_pos
                # Identify leading/trailing separator
                leading_sep = not token_types[start][0]
                trailing_sep = not token_types[end][0]
                for pos_in_match in range(start, end+1):
                    if pos_in_match == start and leading_sep:
                        continue
                    if pos_in_match == end and trailing_sep:
                        continue
                    result[pos_in_match][1].update(node.dict_entries)
            curr_pos += 1
            k += 1

    # Now, annotate single-word tokens with their dictionary entries if any
    for i, (tok, ann) in enumerate(result):
        is_word, normval = token_types[i]
        if is_word:
            node = root.children.get((_WORD, normval))
            if node and node.dict_entries:
                ann.update(node.dict_entries)

    # Return as required
    return result
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


