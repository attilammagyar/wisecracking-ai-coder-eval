# --- BEGIN GENERATED CODE ---
import collections.abc

# ------------------------- internals (helpers) -------------------------

class _TrieNode:
    __slots__ = ("children", "ids", "depth")
    def __init__(self, depth: int = 0):
        self.children = {}  # word(str) -> _TrieNode
        self.ids = set()    # set of dictionary entry ids ending here
        self.depth = depth  # number of words to reach this node

class _DictionaryIndex:
    __slots__ = ("phrase_root", "phrase_word_prefixes", "single_words", "single_word_prefixes")
    def __init__(self):
        self.phrase_root = _TrieNode(depth=0)
        self.phrase_word_prefixes = set()  # prefixes for words that appear inside phrases
        self.single_words = {}             # word(str) -> set(ids)
        self.single_word_prefixes = set()  # prefixes for single_word entries

def _split_words_lower(s: str) -> list[str]:
    s = s.lower()
    out = []
    cur = []
    for ch in s:
        if ch.isalnum():
            cur.append(ch)
        else:
            if cur:
                out.append("".join(cur))
                cur = []
    if cur:
        out.append("".join(cur))
    return out

def _add_prefixes(word: str, dest_set: set):
    # Add all non-empty prefixes
    for k in range(1, len(word) + 1):
        dest_set.add(word[:k])

def _is_word_token(tok: str) -> bool:
    # Word token = all chars are alphanumeric and token non-empty
    if not tok:
        return False
    for ch in tok:
        if not ch.isalnum():
            return False
    return True

# ---------------------- public API implementation ----------------------

def build_dictionary_index(dictionary: collections.abc.Mapping) -> object:
    """
    Build a normalized index from a dictionary for fast lookup of words and
    compound phrases.

    Parameters:
        dictionary: Mapping strings (keys) to meanings (values).
    """
    idx = _DictionaryIndex()

    # First pass: collect single-word entries and phrase entries
    for key, entry_id in dictionary.items():
        words = _split_words_lower(key)
        if not words:
            continue
        if len(words) == 1:
            w = words[0]
            s = idx.single_words.get(w)
            if s is None:
                s = set()
                idx.single_words[w] = s
            s.add(entry_id)
        else:
            # Insert into phrase trie
            node = idx.phrase_root
            for depth, w in enumerate(words, start=1):
                child = node.children.get(w)
                if child is None:
                    child = _TrieNode(depth=depth)
                    node.children[w] = child
                node = child
            node.ids.add(entry_id)
            # Track prefixes for pruning during matching
            for w in words:
                _add_prefixes(w, idx.phrase_word_prefixes)

    # Build single-word prefixes for pruning compound-word concatenations
    for w in idx.single_words.keys():
        _add_prefixes(w, idx.single_word_prefixes)

    return idx

def annotate(tokens: collections.abc.Iterable[str], dictionary_index: object) -> collections.abc.Iterable[tuple[str, collections.abc.Set]]:
    """
    Annotate tokens with entries from the dictionary.

    Parameters:
        dictionary_index:   A dictionary index created by build_dictionary_index()
        tokens:             The tokens to be annotated.

    Return:
        annotated_tokens:   A list containing (token, annotations) pairs for each token in tokens.
    """
    # Convert to list for random access
    toks = list(tokens)
    n = len(toks)
    anns = [set() for _ in range(n)]
    if n == 0:
        return []

    idx = dictionary_index  # type: ignore

    # Classify tokens and prepare lowercase forms for word tokens
    is_word = [_is_word_token(t) for t in toks]
    low = [t.lower() if is_word[i] else None for i, t in enumerate(toks)]

    # 1) Single-word direct matches (per-token)
    sw_map = idx.single_words
    for i in range(n):
        if is_word[i]:
            ids = sw_map.get(low[i])
            if ids:
                anns[i].update(ids)

    # 2) Compound words across adjacent word tokens (no separators in between)
    # Iterate over runs of consecutive word tokens to avoid crossing separators
    i = 0
    sw_prefixes = idx.single_word_prefixes
    while i < n:
        if not is_word[i]:
            i += 1
            continue
        # Find end of the current word-run
        j = i
        while j + 1 < n and is_word[j + 1]:
            j += 1
        # For each start position in the run, try to grow concatenation
        for start in range(i, j + 1):
            s = ""
            for end in range(start, j + 1):
                s += low[end]  # type: ignore
                ids = sw_map.get(s)
                if ids:
                    for p in range(start, end + 1):
                        anns[p].update(ids)
                if s not in sw_prefixes:
                    break  # cannot grow further
        i = j + 1

    # 3) Phrase/compound phrase matching using word-trie (words separated by >=1 separators)
    root = idx.phrase_root
    pw_prefixes = idx.phrase_word_prefixes

    # Helper to annotate matched phrase ranges
    def _annotate_phrase(ids_set, word_spans, sep_spans):
        # word_spans: list of (start,end) indices covering word tokens of each phrase word
        # sep_spans: list of (start,end) indices covering inner separator tokens
        for entry_id in ids_set:
            for a, b in word_spans:
                for p in range(a, b + 1):
                    anns[p].add(entry_id)
            for a, b in sep_spans:
                for p in range(a, b + 1):
                    anns[p].add(entry_id)

    # Recursive exploration to extend a phrase after having matched the last phrase-word
    def _extend(node: _TrieNode, last_word_end: int, sep_start: int, word_spans: list, sep_spans: list):
        # Must have at least one separator
        if sep_start >= n or is_word[sep_start]:
            return
        # Consume full separator run [sep_start .. sep_end]
        sep_end = sep_start
        while sep_end + 1 < n and not is_word[sep_end + 1]:
            sep_end += 1
        next_word_start = sep_end + 1
        if next_word_start >= n or not is_word[next_word_start]:
            return  # no next word to continue phrase

        # Determine end of next word-run to allow multi-token word-chunks
        run_end = next_word_start
        while run_end + 1 < n and is_word[run_end + 1]:
            run_end += 1

        s = ""
        for e in range(next_word_start, run_end + 1):
            s += low[e]  # type: ignore
            if s not in pw_prefixes:
                break
            child = node.children.get(s)
            if child is None:
                continue
            new_words = word_spans + [(next_word_start, e)]
            new_seps = sep_spans + [(sep_start, sep_end)]

            if child.ids:
                _annotate_phrase(child.ids, new_words, new_seps)

            # Try to extend further only if there's at least one following separator
            next_sep_start = e + 1
            if next_sep_start < n and not is_word[next_sep_start]:
                _extend(child, e, next_sep_start, new_words, new_seps)

    # Start matching at every word token; allow multi-token first word-chunk
    for start in range(n):
        if not is_word[start]:
            continue
        # Find end of current word-run to allow concatenation for the first phrase word
        run_end = start
        while run_end + 1 < n and is_word[run_end + 1]:
            run_end += 1

        s = ""
        for e in range(start, run_end + 1):
            s += low[e]  # type: ignore
            if s not in pw_prefixes:
                break
            node = root.children.get(s)
            if node is None:
                continue
            # Need at least one separator after the first word to continue as a phrase
            sep_start = e + 1
            if sep_start < n and not is_word[sep_start]:
                _extend(node, e, sep_start, [(start, e)], [])

    # Build final list of tuples
    annotated_tokens = [(toks[i], anns[i]) for i in range(n)]
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


