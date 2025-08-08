# --- BEGIN GENERATED CODE ---
import collections.abc

# ---------- Helpers and data structures ----------

def _is_word_token(token: str) -> bool:
    # A "word token" contains only alphanumeric characters (no punctuation/whitespace).
    # Keep it simple and consistent with tests.
    return bool(token) and all(ch.isalnum() for ch in token)


def _normalize_words(s: str) -> list[str]:
    # Split a dictionary key into a list of words by removing non-alnum separators.
    # Lowercase with casefold() for case-insensitive matching.
    words = []
    buf = []
    for ch in s:
        if ch.isalnum():
            buf.append(ch)
        else:
            if buf:
                words.append(''.join(buf).casefold())
                buf = []
    if buf:
        words.append(''.join(buf).casefold())
    return words


class _TrieNode:
    __slots__ = ("children", "term_ids")
    def __init__(self):
        self.children: dict[str, _TrieNode] = {}
        self.term_ids: set = set()


class _DictIndex:
    __slots__ = ("root", "single_map", "single_prefixes")
    def __init__(self, root: _TrieNode, single_map: dict[str, set], single_prefixes: set[str]):
        self.root = root
        self.single_map = single_map
        self.single_prefixes = single_prefixes


# ---------- Public API ----------

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.

    Parameters:
        dictionary: Mapping strings (keys) to meanings (values).
    """
    root = _TrieNode()
    single_map: dict[str, set] = {}

    for key, value in dictionary.items():
        words = _normalize_words(str(key))
        if not words:
            continue
        # Build trie path
        node = root
        for w in words:
            node = node.children.setdefault(w, _TrieNode())
        node.term_ids.add(value)
        # Collect single-word entries
        if len(words) == 1:
            single_map.setdefault(words[0], set()).add(value)

    # Build prefix set for single-word dictionary words
    single_prefixes = set()
    for w in single_map.keys():
        # include all non-empty prefixes
        for i in range(1, len(w) + 1):
            single_prefixes.add(w[:i])

    return _DictIndex(root, single_map, single_prefixes)


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.

    Parameters:
        dictionary_index:   A dictionary index created by build_dictionary_index()
        tokens:             The tokens to be annotated.

    Return:
        annotated_tokens:   A list containing (token, annotations) pairs for each token in tokens.
    """
    toks = list(tokens)
    n = len(toks)
    if n == 0:
        return []

    idx = dictionary_index
    root: _TrieNode = idx.root
    single_map: dict[str, set] = idx.single_map
    single_prefixes: set[str] = idx.single_prefixes

    # Prepare annotation sets
    ann = [set() for _ in range(n)]
    # Case-folded tokens for concatenation
    cf = [t.casefold() for t in toks]
    # Build runs: alternating word-runs and separator-runs
    runs = []  # list of tuples: (kind, start, end) where kind in ('w', 's') and end is exclusive
    i = 0
    while i < n:
        is_word = _is_word_token(toks[i])
        kind = 'w' if is_word else 's'
        j = i + 1
        while j < n and _is_word_token(toks[j]) == is_word:
            j += 1
        runs.append((kind, i, j))
        i = j

    # Extract word-runs with their concatenated string
    word_runs = []  # list of dicts with keys: start, end, text
    for kind, start, end in runs:
        if kind == 'w':
            word_runs.append({
                "start": start,
                "end": end,
                "text": ''.join(cf[start:end])
            })

    # -------- Pass 1: single-word matches (within a word-run) --------
    # Try all concatenations of whole tokens within each word-run.
    for wr in word_runs:
        s, e = wr["start"], wr["end"]
        # For each start token position inside the run
        for i in range(s, e):
            curr = ""
            # Extend to the right within this run
            for j in range(i, e):
                curr += cf[j]
                if curr not in single_prefixes:
                    break  # no longer a prefix of any single-word dict entry
                if curr in single_map:
                    ids = single_map[curr]
                    for k in range(i, j + 1):
                        ann[k].update(ids)

    # -------- Pass 2: multi-word phrase matches (across runs) --------
    # Allow a phrase to start at any token position inside a word-run,
    # but the first word must consume from that position to the end of its run.
    # Subsequent words must match entire following word-runs.
    if word_runs:
        # Precompute suffix strings for each word-run to avoid repeated joins
        run_suffixes = []  # list parallel to word_runs, each is list of suffix strings for positions in [start,end)
        for wr in word_runs:
            s, e = wr["start"], wr["end"]
            # Build suffix strings from each token position to the end of the run
            suffixes = [''] * (e - s)
            acc = ''
            # Build backwards to reuse concatenation
            for offset in range(e - s - 1, -1, -1):
                acc = cf[s + offset] + acc
                suffixes[offset] = acc
            run_suffixes.append(suffixes)

        # Multi-word scan
        W = len(word_runs)
        for r_idx in range(W):
            wr = word_runs[r_idx]
            s_token, end_token = wr["start"], wr["end"]
            # For all possible start positions inside this run
            for offset in range(end_token - s_token):
                start_pos = s_token + offset
                first_word = run_suffixes[r_idx][offset]
                node = root.children.get(first_word)
                if node is None:
                    continue  # no phrase starts with this first word
                depth = 1  # number of words matched so far
                # Extend over subsequent word-runs
                j = r_idx
                while j + 1 < W:
                    j += 1
                    next_wr = word_runs[j]
                    node = node.children.get(next_wr["text"])
                    if node is None:
                        break
                    depth += 1
                    # Record only multi-word phrases (depth >= 2)
                    if node.term_ids:
                        # Annotate all tokens from start_pos through the end of current run j
                        for k in range(start_pos, next_wr["end"]):
                            ann[k].update(node.term_ids)

    # Build result
    annotated_tokens = [(toks[i], ann[i]) for i in range(n)]
    return annotated_tokens
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


