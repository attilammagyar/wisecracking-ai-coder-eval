# --- BEGIN GENERATED CODE ---
import collections.abc
from typing import Dict, Set, List, Tuple, Iterable, Optional


def _is_word_token(tok: str) -> bool:
    # Treat token as a "word" if it's composed entirely of alphanumeric chars.
    # Everything else (spaces, punctuation, markdown, etc.) is a separator.
    return len(tok) > 0 and all(ch.isalnum() for ch in tok)


def _split_words_normalized(s: str) -> List[str]:
    # Split dictionary key into "words" by non-alphanumeric separators.
    # Lowercase via casefold for robust case-insensitivity.
    s = s.casefold()
    out = []
    cur = []
    for ch in s:
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append(''.join(cur))
                cur = []
    if cur:
        out.append(''.join(cur))
    return out


class _TrieNode:
    __slots__ = ("children", "ids")
    def __init__(self):
        self.children: Dict[str, _TrieNode] = {}
        self.ids: Set = set()


def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.

    Parameters:
        dictionary: Mapping strings (keys) to meanings (values).
    """
    root = _TrieNode()
    word_to_ids: Dict[str, Set] = {}

    for key, meaning in dictionary.items():
        words = _split_words_normalized(key)
        if not words:
            continue  # purely separators; ignore
        # Insert into trie
        node = root
        for w in words:
            node = node.children.setdefault(w, _TrieNode())
        node.ids.add(meaning)
        # Single-word map
        if len(words) == 1:
            word_to_ids.setdefault(words[0], set()).add(meaning)

    return {"root": root, "word_ids": word_to_ids}


def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.

    Parameters:
        dictionary_index:   A dictionary index created by build_dictionary_index()
        tokens:             The tokens to be annotated.

    Return:
        annotated_tokens:   A list containing (token, annotations) pairs for each token in tokens.
    """
    tokens = list(tokens)
    n = len(tokens)
    ann: List[Set] = [set() for _ in range(n)]
    if n == 0:
        return []

    idx_root: _TrieNode = dictionary_index["root"]
    word_ids: Dict[str, Set] = dictionary_index["word_ids"]

    # Normalize tokens and classify.
    norms: List[str] = [t.casefold() for t in tokens]
    is_word: List[bool] = [_is_word_token(t) for t in tokens]

    # Segment tokens into alternating word/separator runs.
    segments: List[Tuple[bool, int, int]] = []  # (is_word_run, start_idx, end_idx)
    i = 0
    while i < n:
        kind = is_word[i]
        start = i
        i += 1
        while i < n and is_word[i] == kind:
            i += 1
        end = i - 1
        segments.append((kind, start, end))

    # Build word runs and separator runs after each word run.
    word_runs: List[Tuple[int, int]] = []
    sep_after: List[Optional[Tuple[int, int]]] = []  # sep range after each word run, or None
    for si, (isw, s, e) in enumerate(segments):
        if isw:
            word_runs.append((s, e))
            # Look ahead: if next segment exists and is separator
            if si + 1 < len(segments) and not segments[si + 1][0]:
                sep_after.append((segments[si + 1][1], segments[si + 1][2]))
            else:
                sep_after.append(None)

    # Pass 1: single-word matches (including concatenations within a word run).
    # For each word run, consider all substrings (s..e) formed by concatenating adjacent word tokens.
    for (a, b) in word_runs:
        # Incremental building to avoid quadratic joins per substring.
        for s in range(a, b + 1):
            acc = ""
            for e in range(s, b + 1):
                acc += norms[e]
                ids = word_ids.get(acc)
                if ids:
                    for j in range(s, e + 1):
                        ann[j].update(ids)

    # Precompute, per word run, strings from run-start to each end (from_start),
    # and from each start to run-end (to_end). Useful for phrase matching.
    from_start: List[List[Tuple[int, str]]] = []  # per run: list of (abs_end_idx, string)
    to_end: List[List[Tuple[int, str]]] = []      # per run: list of (abs_start_idx, string)
    for (a, b) in word_runs:
        w = norms[a:b + 1]
        # From start
        fs = []
        acc = ""
        for off, tok in enumerate(w):
            acc += tok
            fs.append((a + off, acc))
        from_start.append(fs)
        # To end
        te = []
        # We'll compute suffix strings via join once per start
        for off in range(len(w)):
            sidx = a + off
            te.append((sidx, ''.join(w[off:])))
        to_end.append(te)

    # Helper to apply phrase IDs to the appropriate tokens: all words participating,
    # and only inner separators (no leading/trailing separators).
    def apply_phrase_ids(run_i: int, start_token: int, run_k: int, end_token: int, ids: Set):
        # Words
        ai, bi = word_runs[run_i]
        ak, bk = word_runs[run_k]
        if run_i == run_k:
            # Single-run phrase (should be >=2 words? This helper is used only for multi-word phrases)
            for j in range(start_token, end_token + 1):
                ann[j].update(ids)
        else:
            # First run: from chosen start to end of that run
            for j in range(start_token, bi + 1):
                ann[j].update(ids)
            # Middle runs
            for r in range(run_i + 1, run_k):
                r_a, r_b = word_runs[r]
                for j in range(r_a, r_b + 1):
                    ann[j].update(ids)
            # Last run: from start of last run to chosen end
            for j in range(ak, end_token + 1):
                ann[j].update(ids)
            # Inner separators
            for r in range(run_i, run_k):
                sep = sep_after[r]
                if sep is not None:
                    ssep, esep = sep
                    for j in range(ssep, esep + 1):
                        ann[j].update(ids)

    # Pass 2: multi-word phrases via trie across word runs.
    # We only consider phrases with >= 2 words here.
    # Strategy:
    #  - Choose a starting word run i and a first-word candidate ending at end of run i
    #    (so there's a separator before the next word).
    #  - Then recursively choose last-word endings in subsequent runs (must start at each run's start),
    #    marking a phrase whenever the trie node is terminal and we've consumed >=2 words.
    if word_runs:
        def extend(node: _TrieNode, k: int, start_run_idx: int, start_token_idx: int, word_count_so_far: int):
            # At word run k, try all endings from run-start to e (inclusive).
            # If ending at the run end and there's another run, we may continue.
            fs_list = from_start[k]
            run_end = word_runs[k][1]
            for e_idx, s_str in fs_list:
                next_node = node.children.get(s_str)
                if not next_node:
                    continue
                wc = word_count_so_far + 1
                if wc >= 2 and next_node.ids:
                    apply_phrase_ids(start_run_idx, start_token_idx, k, e_idx, next_node.ids)
                # Continue only if we've consumed entire run k and there is a following run + separator.
                if e_idx == run_end and (k + 1) < len(word_runs) and sep_after[k] is not None:
                    extend(next_node, k + 1, start_run_idx, start_token_idx, wc)

        # Iterate potential starting runs (must have a following sep + run).
        for i_run in range(len(word_runs) - 1):
            if sep_after[i_run] is None:
                continue  # no separator => can't form multi-word phrase starting here
            # First word must go to end of run i_run. Try all possible starts within that run.
            for s_idx, str_to_end in to_end[i_run]:
                first_node = idx_root.children.get(str_to_end)
                if not first_node:
                    continue
                # We require at least another word, so we don't emit yet (phrases >= 2 words).
                extend(first_node, i_run + 1, i_run, s_idx, 1)

    return [(tok, ann_i) for tok, ann_i in zip(tokens, ann)]
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


