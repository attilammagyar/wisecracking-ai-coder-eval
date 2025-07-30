# --- BEGIN GENERATED CODE ---
import collections.abc
import re

WORD_RE = re.compile(r"\w+$")

def is_word_token(token):
    return bool(WORD_RE.match(token))

# Special marker for any separator
SEP = None

def normalize_token(token):
    return token.lower()

def tokenize_phrase(phrase):
    """
    Split dictionary phrase into a list of normalized units:
    words -> normalized string, separators -> SEP.
    E.g. "Hello, world" -> ["hello", SEP, "world"]
    """
    result = []
    i = 0
    while i < len(phrase):
        if phrase[i].isalnum() or phrase[i] == "_":
            # It's the start of a word
            j = i
            while j < len(phrase) and (phrase[j].isalnum() or phrase[j] == "_"):
                j += 1
            result.append(phrase[i:j].lower())
            i = j
        else:
            # It's a separator
            j = i
            while j < len(phrase) and not (phrase[j].isalnum() or phrase[j] == "_"):
                j += 1
            result.append(SEP)
            i = j
    # Remove leading/trailing separators
    while result and result[0] is SEP:
        result.pop(0)
    while result and result[-1] is SEP:
        result.pop()
    # Collapse multiple adjacent SEPs
    normalized_result = []
    for unit in result:
        if unit is SEP:
            if not normalized_result or normalized_result[-1] is not SEP:
                normalized_result.append(SEP)
            # else skip duplicates
        else:
            normalized_result.append(unit)
    return normalized_result

class TrieNode:
    __slots__ = ("children", "entries")
    def __init__(self):
        self.children = dict()  # {token or SEP: TrieNode}
        self.entries = set()    # set of dictionary indices/numbers

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index (Trie) from the dictionary for fast phrase lookup.
    """
    # All keys and values are iterated just once, so no perf worries here
    trie_root = TrieNode()
    word_entry_lookup = collections.defaultdict(set)
    max_phrase_len = 1  # Used for micro-optimization (not strictly required)

    for phrase, value in dictionary.items():
        normalized = tokenize_phrase(phrase)
        if not normalized:
            continue
        node = trie_root
        for unit in normalized:
            if unit not in node.children:
                node.children[unit] = TrieNode()
            node = node.children[unit]
        node.entries.add(value)

        # For direct word lookup, for any single-word phrase, cache it
        if len(normalized) == 1:
            word_entry_lookup[normalized[0]].add(value)
        if len(normalized) > max_phrase_len:
            max_phrase_len = len(normalized)

    # Pack the resulting index
    return {
        "trie_root": trie_root,
        "word_entry_lookup": word_entry_lookup,
        "max_phrase_len": max_phrase_len,  # Technically optional, could help perf
    }

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary, including compounds.
    """
    tokens = list(tokens)
    n = len(tokens)
    trie_root = dictionary_index["trie_root"]
    word_entry_lookup = dictionary_index["word_entry_lookup"]

    # For each token, build initial annotation set
    annotations = [set() for _ in tokens]

    # 1. Single-token direct lookups
    for i, token in enumerate(tokens):
        if is_word_token(token):
            norm = normalize_token(token)
            entries = word_entry_lookup.get(norm)
            if entries:
                annotations[i].update(entries)

    # 2. Compound phrase lookup via Trie
    # We scan starting from *every* position, matching as deep as possible in Trie
    i = 0
    while i < n:
        # Only word or separator tokens can be at any position
        # We always start compound matching from a word token
        if not is_word_token(tokens[i]):
            i += 1
            continue

        # For each position, walk the Trie as far as phrases allow
        trie_nodes = [(trie_root, i, [])]  # (trie node, token index, match_indices)
        while trie_nodes:
            node, idx, match_indices = trie_nodes.pop()

            # If at least one word matched, and we are at a Trie node with entry, it's a match!
            # The 'match_indices' tells us which input tokens are part of the phrase, including inner separators
            if node.entries and match_indices:
                # Only add annotation to non-leading/trailing separators
                # Edge case: if match_indices is [i], it's a single word, already handled above
                # But no harm annotating again, as sets deduplicate; but spec wants both single and compound entries
                # So, for all match_indices, but skip if leading/trailing separator for compounds
                # For multi-token, 
                first, last = match_indices[0], match_indices[-1]
                for pos in match_indices:
                    # Compound: skip leading/trailing separators
                    if len(match_indices) > 1 and not is_word_token(tokens[pos]):
                        if pos == first or pos == last:
                            continue
                    # Otherwise, annotate
                    annotations[pos].update(node.entries)

            # Now, try to expand match: Either to a word or to a separator
            if idx >= n:
                continue

            curr_token = tokens[idx]

            # Option A: Next Trie child is a word, and current token matches
            if is_word_token(curr_token):
                norm = normalize_token(curr_token)
                if norm in node.children:
                    trie_nodes.append(
                        (node.children[norm], idx+1, match_indices + [idx])
                    )

            # Option B: Next Trie child is SEP, and current token is a separator
            if SEP in node.children:
                # Only traverse SEPs on *sequences* of separators
                sep_start = idx
                while idx < n and not is_word_token(tokens[idx]):
                    idx +=1
                if idx > sep_start:
                    # Add entire run of separators as a single SEP step
                    # We allow matches like ["word", " ", "*", "word"] as a compound with one SEP
                    trie_nodes.append(
                        (node.children[SEP], idx, match_indices + list(range(sep_start, idx)))
                    )
        i += 1

    # Output final (token, annotations) pairs
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


