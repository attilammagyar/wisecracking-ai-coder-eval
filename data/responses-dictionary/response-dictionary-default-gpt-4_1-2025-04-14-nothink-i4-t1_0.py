# --- BEGIN GENERATED CODE ---
import collections.abc
import re

# Constants for Trie
_SEP = "__SEP__"  # marker for a separator position in normalized phrases

def is_word(token):
    """Heuristic: a token is a 'word' if it has any alphanumeric chars."""
    return any(c.isalnum() for c in token)

def normalize_token(token):
    """Normalize for comparison: lower-case, but don't alter content."""
    return token.lower()

def normalize_phrase(phrase):
    """
    Given a phrase from the dictionary, split into a sequence of normalized tokens,
    marking non-word separators as _SEP.
    E.g., "AAA, BBB" -> ['aaa', _SEP, 'bbb']
    """
    # Split into "word" and "separator" runs:
    result = []
    idx = 0
    while idx < len(phrase):
        # Match word
        m = re.match(r'\w+', phrase[idx:], re.UNICODE)
        if m:
            result.append(normalize_token(m.group(0)))
            idx += m.end()
            continue
        # Match separator (non-word): skip over all adjacent non-word chars
        m = re.match(r'\W+', phrase[idx:], re.UNICODE)
        if m:
            result.append(_SEP)
            idx += m.end()
            continue
        # Defensive: if stuck, skip one char
        idx += 1
    # Strip leading/trailing separators (don't want matches with them)
    while result and result[0] == _SEP:
        result.pop(0)
    while result and result[-1] == _SEP:
        result.pop()
    return result

class TrieNode:
    __slots__ = ['children', 'dict_ids']
    def __init__(self):
        self.children = dict()   # key: str (token or _SEP), value: TrieNode
        self.dict_ids = set()    # set of dictionary entry ids (for end-of-phrase)

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a case-normalized Trie where each edge is a word (lowercased) or _SEP.
    Each final node (`dict_ids`) contains the id(s) of the phrase matched.
    """
    trie = TrieNode()
    for key, value in dictionary.items():
        phrase_seq = normalize_phrase(key)
        if not phrase_seq:
            continue   # Skip empty
        node = trie
        for tok in phrase_seq:
            if tok not in node.children:
                node.children[tok] = TrieNode()
            node = node.children[tok]
        node.dict_ids.add(value)
    return trie

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with dictionary entries:
    - Annotate with phrase id if token is part of a matched phrase (including as an inner separator).
    - Compound phrase match should be maximally inclusive, and all valid phrases (overlapping/nested) included.
    """
    tokens = list(tokens)
    n = len(tokens)
    # Precompute for efficiency:
    norm_tokens = [normalize_token(tok) for tok in tokens]
    is_word_list = [is_word(tok) for tok in tokens]

    # For every token, collect the set of ids it should be annotated with
    annotations = [set() for _ in range(n)]

    trie = dictionary_index

    # To allow O(1) lookup for single word dictionary entries
    # This saves lots of trie-walking for single tokens
    # (More efficient for large dictionaries with lots of single-word entries)
    single_word_lookup = dict()
    node = trie
    for k, child in node.children.items():
        if k != _SEP and child.dict_ids:
            for dict_id in child.dict_ids:
                single_word_lookup[k] = single_word_lookup.get(k, set())
                single_word_lookup[k].add(dict_id)

    # 1. Single-token annotations (individual word lookup)
    for idx, (tok, is_word_flag) in enumerate(zip(norm_tokens, is_word_list)):
        if is_word_flag:
            for dict_id in single_word_lookup.get(tok, set()):
                annotations[idx].add(dict_id)

    # 2. Multi-token (phrase) matches - including overlapping/nested phrases
    # For every possible start position of a "phrase"
    for start in range(n):
        # Skip leading separators (per the rules: leading separators not part of phrases)
        if not is_word_list[start]:
            continue

        positions = [(start, trie, 0)]   # (cur_idx, trie_node, match_len)
        # To find all matches, we use BFS for all possible interleaving of separators
        # Each branch represents continuing to match the Trie from cur_idx
        while positions:
            idx, node, matched = positions.pop()
            # If this node is the end of a phrase in the dictionary, record its ids
            if node.dict_ids:
                # This is potentially a phrase, figure out which tokens are covered
                # We can recover the matched span as: [start, idx)
                # Need to annotate all tokens in this span, EXCEPT leading/trailing separators, only if present
                left = start
                right = idx
                # Identify inner tokens - strip leading/trailing separators
                local_l = left
                local_r = right - 1  # inclusive
                while local_l <= local_r and not is_word_list[local_l]:
                    local_l += 1
                while local_r >= local_l and not is_word_list[local_r]:
                    local_r -= 1
                # Now annotate all in local_l..local_r inclusive
                for i in range(local_l, local_r + 1):
                    annotations[i].update(node.dict_ids)

            # After matching, consider advancing
            # For each child of this node:
            for child_key, child_node in node.children.items():
                if child_key == _SEP:
                    # This child expects a separator: skip at least one separator token
                    next_idx = idx
                    count = 0
                    while next_idx < n and not is_word_list[next_idx]:
                        next_idx += 1
                        count += 1
                    if count >= 1 and next_idx <= n:
                        # After skipping >=1 separators, continue matching
                        positions.append((next_idx, child_node, matched + count))
                else:
                    # This child expects a word
                    if idx < n and is_word_list[idx] and norm_tokens[idx] == child_key:
                        positions.append((idx + 1, child_node, matched + 1))
                    # else: can't match further

    # Prepare output
    return [(tok, annotations[idx]) for idx, tok in enumerate(tokens)]
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


