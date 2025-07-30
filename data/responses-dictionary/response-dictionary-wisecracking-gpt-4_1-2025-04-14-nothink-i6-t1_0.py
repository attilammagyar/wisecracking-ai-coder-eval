# --- BEGIN GENERATED CODE ---
import collections.abc
import re

def _is_word(token):
    # A "word" is any token with at least one alphanumeric character.
    return any(c.isalnum() for c in token)

def _normalize_word(token):
    return token.lower()

def _split_dict_phrase(phrase):
    # Split into alternation of word/separators, remove empty
    # Leading/trailing separators? Yes; we want to record them for matching.
    parts = []
    buff = ''
    last_type = None
    for c in phrase:
        if c.isalnum():
            if last_type == 'word':
                buff += c
            else:
                if buff:
                    parts.append((last_type, buff))
                buff = c
                last_type = 'word'
        else:
            if last_type == 'sep':
                buff += c
            else:
                if buff:
                    parts.append((last_type, buff))
                buff = c
                last_type = 'sep'
    if buff:
        parts.append((last_type, buff))
    # Remove None-typed (init)
    return [(t, v) for t, v in parts if t]

def _normalize_phrase_tokens(phrase):
    # Returns the alternation of groups: ('word', word), ('sep', sep)
    segs = []
    for m in re.finditer(r'\w+|\W+', phrase, re.UNICODE):
        w = m.group(0)
        if _is_word(w):
            segs.append(('word', _normalize_word(w)))
        else:
            segs.append(('sep', w))
    return segs

def _normalize_phrase_tokens_compact(phrase):
    # Produces: [token_type, ...] flattening the actual values, but preserving alternating types
    segs = []
    for m in re.finditer(r'\w+|\W+', phrase, re.UNICODE):
        w = m.group(0)
        if _is_word(w):
            segs.append(('word', _normalize_word(w)))
        else:
            segs.append(('sep', None))  # We don't care about exact separator
    return segs

def build_dictionary_index(dictionary):
    """
    Build a normalized index from a dictionary for fast lookup of words and compound phrases.
    We'll store the following:
    - A trie for phrases, where each node marks if it's an end of a dictionary entry,
      and stores a set of entry IDs for that phrase.
    - A dict for single-token entries: normalized word -> set of entry IDs.
    """
    # Trie node: {'children': {key: node, ...}, 'entries': set(dict_ids)}
    class TrieNode:
        __slots__ = ('children', 'entries')
        def __init__(self):
            self.children = {}
            self.entries = set()
    root = TrieNode()
    single_word = collections.defaultdict(set)

    for phrase, entid in dictionary.items():
        # Tokenize as alternation of word and separator; normalize words (lowercase)
        segs = []
        for m in re.finditer(r'\w+|\W+', phrase, re.UNICODE):
            w = m.group(0)
            if _is_word(w):
                segs.append(('word', _normalize_word(w)))
            else:
                segs.append(('sep', None))  # Normalize: all sep treated same
        
        # Store in trie:
        node = root
        for kind, tok in segs:
            k = (kind, tok if kind == 'word' else None)
            if k not in node.children:
                node.children[k] = TrieNode()
            node = node.children[k]
        node.entries.add(entid)

        # If it's exactly one normalized word, add it to single_word dict for fast lookup.
        nonsep = [tok for kind, tok in segs if kind == 'word']
        if len(nonsep) == 1 and len(segs) == 1:
            single_word[nonsep[0]].add(entid)

    return {'trie': root, 'single_word': dict(single_word)}

def annotate(tokens, dictionary_index):
    trie = dictionary_index['trie']
    single_word = dictionary_index['single_word']
    annotated = [set() for _ in tokens]

    # Precompute token types/normalized forms for minimal double-work.
    token_types = [_is_word(tok) for tok in tokens]  # True for word, False for sep
    norm_tokens = [_normalize_word(tok) if isw else None for tok, isw in zip(tokens, token_types)]

    n = len(tokens)

    # 1. Annotate individual tokens
    for i, (isw, norm) in enumerate(zip(token_types, norm_tokens)):
        if isw and norm in single_word:
            annotated[i].update(single_word[norm])

    # 2. Annotate compound phrases: walk trie from every word token (also from positions with leading/trailing sep)
    for start in range(n):
        node = trie
        i = start
        segidx = 0
        # Record the indices of word and sep tokens
        positions = []
        while i < n:
            isw = token_types[i]
            if isw:
                k = ('word', norm_tokens[i])
            else:
                k = ('sep', None)
            if k not in node.children:
                break
            node = node.children[k]
            positions.append(i)
            segidx += 1
            # Only match if phrase ends at this span
            if node.entries:
                # Find indices for annotation following "inner separator" rules:
                # - For a span [start, i], annotate all word tokens, and separators except if leading or trailing
                # - If the span's first token is a separator, don't annotate; trailing separator: don't annotate
                first, last = positions[0], positions[-1]
                # Pick separator tokens in the span, except at the boundaries
                for idx, j in enumerate(positions):
                    if token_types[j]:
                        # always annotate word tokens
                        annotated[j].update(node.entries)
                    else:
                        # Only annotate separator if not first or last in phrase
                        if idx != 0 and idx != len(positions) - 1:
                            annotated[j].update(node.entries)
            i += 1

    # 3. Output as (token, set) pairs.
    return [(tok, ann) for tok, ann in zip(tokens, annotated)]
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


