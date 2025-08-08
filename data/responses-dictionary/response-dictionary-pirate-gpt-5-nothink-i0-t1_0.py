# --- BEGIN GENERATED CODE ---
import collections.abc

# ----------------------------
# Helpers (internal)
# ----------------------------

def _extract_words_lower(s: str) -> list[str]:
    """
    Split a string into lowercase alphanumeric words.
    Non-alphanumeric runes are treated as separators.
    """
    words = []
    buf = []
    for ch in s:
        if ch.isalnum():
            buf.append(ch.lower())
        else:
            if buf:
                words.append("".join(buf))
                buf.clear()
    if buf:
        words.append("".join(buf))
    return words


def _is_word_token(tok: str) -> bool:
    """
    A token is a word token iff it consists only of alphanumerics.
    """
    if not tok:
        return False
    # All chars must be alphanumeric; this forbids mid-token matches.
    return all(c.isalnum() for c in tok)


class _TrieNode:
    __slots__ = ("children", "values")
    def __init__(self):
        self.children: dict[str, _TrieNode] = {}
        self.values: set = set()


def _insert_in_trie(root: _TrieNode, words: list[str], val):
    node = root
    for w in words:
        child = node.children.get(w)
        if child is None:
            child = _TrieNode()
            node.children[w] = child
        node = child
    node.values.add(val)


# ----------------------------
# Public API
# ----------------------------

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized trie index from the dictionary for fast phrase lookup.
    Keys are split into lowercase alphanumeric words; punctuation and spacing
    are treated as separators.
    """
    root = _TrieNode()
    for key, val in dictionary.items():
        words = _extract_words_lower(key)
        if words:  # ignore entries that yield no words
            _insert_in_trie(root, words, val)
    return root


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with dictionary entries (both single words and phrases).
    Matching rules:
      - Case-insensitive.
      - Dictionary words are alphanumeric runs; dictionary separators ignored.
      - Matches occur only at token boundaries (no mid-token matches).
      - A dictionary "word" may be formed by concatenating adjacent word tokens with no separators.
      - Multi-word phrases require at least one separator token between words in text.
      - Annotate inner separators of matched phrases, never leading or trailing separators.
    """
    tokens = list(tokens)
    n = len(tokens)
    if n == 0:
        return []

    root: _TrieNode = dictionary_index  # the trie root

    # Classify tokens
    is_word = [_is_word_token(t) for t in tokens]
    lower_tok = [t.lower() if is_word[i] else None for i, t in enumerate(tokens)]

    # Prepare per-token annotation sets
    annos = [set() for _ in range(n)]

    # Positions of word tokens
    word_pos = [i for i in range(n) if is_word[i]]
    wcount = len(word_pos)
    if wcount == 0:
        # No word tokens => nothing to match; everything stays empty
        return list(zip(tokens, annos))

    # Adjacent flags between consecutive word tokens: True iff no separators between
    # (i.e., the word tokens are consecutive tokens in the stream).
    adjacent = [False] * wcount
    for k in range(wcount - 1):
        adjacent[k] = (word_pos[k] + 1 == word_pos[k + 1])

    # Run ends for each word-token index: last index in the same adjacency-run
    run_end = [0] * wcount
    for p in range(wcount):
        q = p
        while q < wcount - 1 and adjacent[q]:
            q += 1
        run_end[p] = q

    # Utility to add a match's IDs to all involved tokens:
    def add_match(ids: collections.abc.Iterable, tok_start_idx: int, tok_end_idx: int):
        # Add to word tokens in [tok_start_idx, tok_end_idx]
        for i in range(tok_start_idx, tok_end_idx + 1):
            if is_word[i]:
                annos[i].update(ids)
        # Add to inner separators strictly between the ends
        for i in range(tok_start_idx + 1, tok_end_idx):
            if not is_word[i]:
                annos[i].update(ids)

    # Depth-first extension for multi-word phrases.
    # node: current trie node after consuming prior dictionary words
    # pw_start: index in word_pos where next dictionary word must start
    # tok_span_start: token index where the whole phrase started (word_pos[p0])
    def dfs_extend(node: _TrieNode, pw_start: int, tok_span_start: int):
        if pw_start >= wcount:
            return
        # The next dictionary word must start after at least one separator from the previous word,
        # guaranteed by caller.
        # Try to consume 1..K adjacent word tokens (no separators) to form the next dictionary word.
        s = ""
        pw_end_max = run_end[pw_start]
        # Build incrementally to avoid repeated joins
        for pw_end in range(pw_start, pw_end_max + 1):
            s += lower_tok[word_pos[pw_end]]
            child = node.children.get(s)
            if child is None:
                break

            # We've matched another dictionary word; record phrase so far
            if child.values:
                tok_end_idx = word_pos[pw_end]
                add_match(child.values, tok_span_start, tok_end_idx)

            # If we can continue (must have at least one separator to the next word)
            if pw_end < wcount - 1 and not adjacent[pw_end]:
                dfs_extend(child, pw_end + 1, tok_span_start)
            # Else, cannot extend; but still continue loop to try longer concatenation for this word

    # Try matches starting at every word token
    for pw0 in range(wcount):
        # First dictionary word can consume 1..K adjacent word tokens from this start.
        s = ""
        first_end_max = run_end[pw0]
        tok_start_idx = word_pos[pw0]
        node0 = root
        for pw_end in range(pw0, first_end_max + 1):
            s += lower_tok[word_pos[pw_end]]
            node1 = node0.children.get(s)
            if node1 is None:
                break

            # Single-word dictionary entry (could span multiple tokens if concatenated)
            if node1.values:
                tok_end_idx = word_pos[pw_end]
                add_match(node1.values, tok_start_idx, tok_end_idx)

            # Multi-word extension requires at least one separator before the next word
            if pw_end < wcount - 1 and not adjacent[pw_end]:
                dfs_extend(node1, pw_end + 1, tok_start_idx)
            # Otherwise, cannot extend multi-word phrase; continue trying larger concatenation for this word

    return list(zip(tokens, annos))
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


